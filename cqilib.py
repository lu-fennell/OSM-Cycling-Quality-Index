from qgis.core import NULL, edit  # type: ignore[attr-defined]


from qgis.core import (
    QgsVectorLayer,
    QgsProcessingFeatureSourceDefinition,
    QgsProcessingFeatureSource,
    QgsVectorLayerSelectedFeatureSource,
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
from pathlib import Path

# TODO: as a parameter maybe?
import definitions as d


def read_layer_geojson(geojson_file: str, name: str | None = None) -> QgsVectorLayer:
    if not Path(geojson_file).exists():
        raise FileNotFoundError(geojson_file)
    if name is not None:
        return QgsVectorLayer(geojson_file, name, "ogr")
    else:
        return QgsVectorLayer(geojson_file, "ogr")


def copy_to_mem_layer(layer: QgsVectorLayer) -> QgsVectorLayer:
    return process_to_mem_layer(
        "qgis:extractbyexpression",
        {"INPUT": layer, "EXPRESSION": "TRUE"},
    )


def process_to_mem_layer(name: str, opts: dict) -> QgsVectorLayer:
    opts = opts.copy()
    opts["OUTPUT"] = "memory:"
    return processing.run(name, opts)["OUTPUT"]


def sidepath_create_layer_path(layer: QgsVectorLayer) -> QgsVectorLayer:
    """create path layer: highway that are in [cycleway, footway, path, bridleway, steps]"""
    return process_to_mem_layer(
        "qgis:extractbyexpression",
        {
            "INPUT": layer,
            "EXPRESSION": "\"highway\" IS 'cycleway' OR \"highway\" IS 'footway' OR \"highway\" IS 'path' OR \"highway\" IS 'bridleway' OR \"highway\" IS 'steps'",
        },
    )


def sidepath_create_layer_roads(layer: QgsVectorLayer) -> QgsVectorLayer:
    """create road layer: extract all other highway types that are not "path" (except tracks)"""
    return process_to_mem_layer(
        "qgis:extractbyexpression",
        {
            "INPUT": layer,
            "EXPRESSION": "\"highway\" IS NOT 'cycleway' AND \"highway\" IS NOT 'footway' AND \"highway\" IS NOT 'path' AND \"highway\" IS NOT 'bridleway' AND \"highway\" IS NOT 'steps' AND \"highway\" IS NOT 'track'",
            "OUTPUT": "memory:",
        },
    )


# TODO: use a proper class for the entries of the dict
def sidepath_dict(
    layer_path_points_buffers: QgsVectorLayer, layer_roads: QgsVectorLayer
) -> dict:
    if QgsProject.instance().mapLayer(layer_path_points_buffers.id()) is None:
        raise ValueError(
            "argument layer_path_points_buffers is not part of the current project"
        )

    sidepath_dict: dict = {}

    for buffer in layer_path_points_buffers.getFeatures():
        buffer_id = buffer.attribute("id")
        buffer_layer = buffer.attribute("layer")
        if buffer_id not in sidepath_dict:
            sidepath_dict[buffer_id] = {}
            sidepath_dict[buffer_id]["checks"] = 1
            sidepath_dict[buffer_id]["id"] = {}
            sidepath_dict[buffer_id]["highway"] = {}
            sidepath_dict[buffer_id]["name"] = {}
            sidepath_dict[buffer_id]["maxspeed"] = {}
        else:
            sidepath_dict[buffer_id]["checks"] += 1
        layer_path_points_buffers.removeSelection()
        layer_path_points_buffers.select(buffer.id())
        # TODO: can I have this without adding the layer to the project?
        feature_source = QgsProcessingFeatureSourceDefinition(
            layer_path_points_buffers.id(), selectedFeaturesOnly=True
        )
        processing.run(
            "native:selectbylocation",
            {
                "INPUT": layer_roads,
                "INTERSECT": feature_source,
                "METHOD": 0,
                "PREDICATE": [0, 6],
            },
        )

        id_list = []
        highway_list = []
        name_list = []
        maxspeed_dict: dict[str, float] = {}
        for road in layer_roads.selectedFeatures():
            road_layer = road.attribute("layer")
            if buffer_layer != road_layer:
                continue  # only consider geometries in the same layer
            road_id = road.attribute("id")
            road_highway = road.attribute("highway")
            road_name = road.attribute("name")
            road_maxspeed = d.getNumber(road.attribute("maxspeed"))
            if road_id not in id_list:
                id_list.append(road_id)
            if road_highway not in highway_list:
                highway_list.append(road_highway)
            if (
                road_highway not in maxspeed_dict
                or maxspeed_dict[road_highway] < road_maxspeed
            ):
                maxspeed_dict[road_highway] = road_maxspeed
            if road_name not in name_list:
                name_list.append(road_name)
        for road_id in id_list:
            if road_id in sidepath_dict[buffer_id]["id"]:
                sidepath_dict[buffer_id]["id"][road_id] += 1
            else:
                sidepath_dict[buffer_id]["id"][road_id] = 1
        for road_highway in highway_list:
            if road_highway in sidepath_dict[buffer_id]["highway"]:
                sidepath_dict[buffer_id]["highway"][road_highway] += 1
            else:
                sidepath_dict[buffer_id]["highway"][road_highway] = 1
        for road_name in name_list:
            if road_name in sidepath_dict[buffer_id]["name"]:
                sidepath_dict[buffer_id]["name"][road_name] += 1
            else:
                sidepath_dict[buffer_id]["name"][road_name] = 1

        for highway in maxspeed_dict.keys():
            if (
                highway not in sidepath_dict[buffer_id]["maxspeed"]
                or sidepath_dict[buffer_id]["maxspeed"][highway]
                < maxspeed_dict[highway]
            ):
                sidepath_dict[buffer_id]["maxspeed"][highway] = maxspeed_dict[highway]

    return sidepath_dict
