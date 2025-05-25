# ---------------------------------------------------------------------------#
#   Cycling Quality Index                                                   #
#   --------------------------------------------------                      #
#   Script for processing OSM data to analyse the cycling quality of ways.  #
#   Download OSM data input from https://overpass-turbo.eu/s/1IDp,          #
#   save it at data/way_import.geojson and run the script.                  #
#                                                                           #
#   > version/date: 2024-04-15                                              #
# ---------------------------------------------------------------------------#

# TODO: how to import this s.t. mypy does not complain?
from qgis.core import NULL, edit  # type: ignore[attr-defined]
from qgis.utils import iface  # type: ignore[import-not-found]
from qgis.core import (
    QgsVectorLayer,
    QgsProcessingFeatureSourceDefinition,
    QgsProperty,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
    QgsField,
)
from PyQt5.QtCore import QVariant
import qgis.processing as processing
import os
import sys
import math
import time
import tracing  # noqa: E402
import cqilib  # noqa: E402
import parameter as p  # noqa: E402
import definitions as d  # noqa: E402
import reload_local_modules
import featuredb_qgis


# --------------------------------
#      S c r i p t   S e t u p
# --------------------------------
  
# TODO: Find a better way to determine the project dir.. maybe through the Qgis project home for now
from console.console import _console  # type: ignore[import-not-found]
project_dir = os.path.dirname(
    _console.console.tabEditorWidget.currentWidget()._editor_code_widget.filePath()
)
reload_local_modules.reload(project_dir)


dir_input = project_dir + "/data/way_import"
dir_output = project_dir + "/data/cycling_quality_index"
file_format = ".geojson"
input_file = f'{dir_input}{file_format}'
multi_input = False  # if "True", it's possible to merge different import files stored in the input directory, marked with an ascending number starting with 1 at the end of the filename (e.g. way_import1.geojson, way_import2.geojson etc.) - can be used to process different areas at the same time or to process a larger area that can't be downloaded in one file

if project_dir not in sys.path:
    sys.path.append(project_dir)

trace = tracing.Trace(f"{project_dir}/traceoutput", "refactored", pretty=True)

# --------------------------------
#      S c r i p t   S t a r t
# --------------------------------

print(time.strftime("%H:%M:%S", time.localtime()), "Start processing:")

print(time.strftime("%H:%M:%S", time.localtime()), "Read data...")

feature_db = featuredb_qgis.QgsFeatureDb(QgsProject.instance())

# layer_way_input = cqilib.read_input(dir_input, file_format, p.attributes_list, multi_input)
feature_set = feature_db.import_geojson(input_file, p.attributes_list)
trace.add_layer(feature_set.to_layer(), "input")

print(time.strftime("%H:%M:%S", time.localtime()), "Reproject and prepare data...")

feature_set.reproject(p.crs_metric)
feature_set.retaintags(set(p.attributes_list))

trace.add_layer(feature_set.to_layer(), "reduced_fields")


cqilib.add_cyling_attributes(feature_set, p.attributes_list)
trace.add_layer(feature_set.to_layer(), "with_extended_attributes")


features_reprojected = feature_set.copy()
layer = feature_set.to_layer()

# ---------------------------------------------------------------#
# 1: Check paths whether they are sidepath (a path along a road) #
# ---------------------------------------------------------------#

print(time.strftime("%H:%M:%S", time.localtime()), "Sidepath check...")
print(time.strftime("%H:%M:%S", time.localtime()), "   Create way layers...")

# create path layer: check all path, footways or cycleways for their sidepath status
#
layer_path = cqilib.sidepath_create_layer_path(features_reprojected.to_layer())
layer_roads = cqilib.sidepath_create_layer_roads(features_reprojected.to_layer())

print(time.strftime("%H:%M:%S", time.localtime()), "   Create check points...")
# create "check points" along each segment (to check for near/parallel highways at every checkpoint)
layer_path_points = cqilib.sidepath_pointsalonglines(layer_path, p.sidepath_buffer_distance)
layer_path_points_endpoints = cqilib.sidepath_extractlastvertex(layer_path)
layer_path_points = cqilib.merge_layers([layer_path_points, layer_path_points_endpoints])
# create "check buffers" (to check for near/parallel highways with in the given distance)
layer_path_points_buffers = cqilib.sidepath_buffer(layer_path_points, p.sidepath_buffer_size)
QgsProject.instance().addMapLayer(layer_path_points_buffers, False)

print(time.strftime("%H:%M:%S", time.localtime()), "   Check for adjacent roads...")

# for all check points: Save nearby road id's, names and highway classes in a dict
sidepath_dict: dict = cqilib.sidepath_dict(layer_path_points_buffers, layer_roads)
trace.add_dict(sidepath_dict, "sidepath_dict")

attrs =  cqilib.attribute_ids(layer)
cqilib.sidepath_classification(
   layer,
   sidepath_dict,
    attrs       
)
trace.add_layer(layer, "sidepaths")

# -------------------------------------------------------------------------------#
# 2: Split and shift attributes/geometries for sidepath mapped on the centerline #
# -------------------------------------------------------------------------------#

print(time.strftime("%H:%M:%S", time.localtime()), "Split line bundles...")
with edit(layer):
    for feature in layer.getFeatures():
        cqilib.sidepath_set_offset_attributes(layer, feature, attrs)

    # TODO: offset als Attribut überschreiben
    # eigenständige Attribute ableiten
    # TODO: don't use strings for dict
    # TODO: probably can be pulled out of the "with" but needs smarter comparison
    offset_layers = cqilib.sidepath_offset_layers(layer)

    layer.updateFields()
trace.add_layer(layer, "split_and_shift")

# TODO: Attribute mit "both" auf left und right aufteilen?
cqilib.sidepath_derive_offset_attrs(offset_layers, attrs)
for side in ["left", "right"]:
    for type in ["cycleway", "sidewalk"]:
        offset_layer = offset_layers[side][type]
        trace.add_layer(offset_layer, f"derived_attributes_{side}_{type}")
# TODO: clean up offset layers

# merge vanilla and offset layers
layer = cqilib.merge_layers([layer]
        + [
            offset_layers[side][type]
            for type in ["cycleway", "sidewalk"]
            for side in ["left", "right"]
        ])
trace.add_layer(layer, "merged")

# --------------------------------------------#
# 3: Determine way type for every way segment #
# --------------------------------------------#

print(time.strftime("%H:%M:%S", time.localtime()), "Determine way type...")
cqilib.determine_way_type(layer, attrs)
trace.add_layer(layer, "with_way_types")

# ----------------------------------------------------#
# 4: Derive relevant attributes for index and factors, and calculate index and factors #
# ----------------------------------------------------#
print(
    time.strftime("%H:%M:%S", time.localtime()),
    "Derive attributes/calculate index...",
)
cqilib.calculate_index(layer, attrs)
trace.add_layer(layer, "after_indexing")

# clean up data set and reproject to output crs
print(time.strftime("%H:%M:%S", time.localtime()), "Clean up data...")
layer = processing.run(
    "native:retainfields",
    {
        "INPUT": layer,
        "FIELDS": p.attributes_list_finally_retained,
        "OUTPUT": "memory:",
    },
)["OUTPUT"]
layer = processing.run(
    "native:reprojectlayer",
    {
        "INPUT": layer,
        "TARGET_CRS": QgsCoordinateReferenceSystem(p.crs_output),
        "OUTPUT": "memory:",
    },
)["OUTPUT"]

print(time.strftime("%H:%M:%S", time.localtime()), "Save output data set...")
QgsVectorFileWriter.writeAsVectorFormat(
    layer,
    dir_output + file_format,
    "utf-8",
    QgsCoordinateReferenceSystem(p.crs_output),
    "GeoJSON",
)
trace.add_layer(layer, "final_result")

print(time.strftime("%H:%M:%S", time.localtime()), "Display data...")
QgsProject.instance().addMapLayer(layer, True)
layer.setName("Cycling Quality Index")
layer.loadNamedStyle(project_dir + "/styles/index.qml")
# focus on output layer
iface.mapCanvas().setExtent(layer.extent())

print(time.strftime("%H:%M:%S", time.localtime()), "Finished processing.")
print(time.strftime("%H:%M:%S", time.localtime()), "Check for regressions")

# TODO: add "ResourceManager" and with(...)
feature_db.close()

import compare_traces  # noqa: E402

# TODO: disable colorize
compare_traces.run(trace.out_dir, f"{trace.tracing_dir}/original")
