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
from dataclasses import dataclass

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

def fixup_input_layer(layer_way_input: QgsVectorLayer, crs_metric: str, attributes_list: list[str]) -> QgsVectorLayer:
    
    layer = processing.run(
        "native:reprojectlayer",
        {
            "INPUT": layer_way_input,
            "TARGET_CRS": QgsCoordinateReferenceSystem(crs_metric),
            "OUTPUT": "memory:",
        },
    )["OUTPUT"]

    # delete unneeded attributes
    layer = processing.run(
        "native:retainfields",
        {"INPUT": layer, "FIELDS": attributes_list, "OUTPUT": "memory:"},
    )["OUTPUT"]
    return layer

new_attributes_dict = {
        "way_type": "String",
        "index": "Int",
        "index_10": "Int",
        "stress_level": "Int",
        "offset": "Double",
        "offset_cycleway_left": "Double",
        "offset_cycleway_right": "Double",
        "offset_sidewalk_left": "Double",
        "offset_sidewalk_right": "Double",
        "type": "String",
        "side": "String",
        "proc_width": "Double",
        "proc_surface": "String",
        "proc_smoothness": "String",
        "proc_oneway": "String",
        "proc_sidepath": "String",
        "proc_highway": "String",
        "proc_maxspeed": "Int",
        "proc_traffic_mode_left": "String",
        "proc_traffic_mode_right": "String",
        "proc_separation_left": "String",
        "proc_separation_right": "String",
        "proc_buffer_left": "Double",
        "proc_buffer_right": "Double",
        "proc_mandatory": "String",
        "proc_traffic_sign": "String",
        "fac_width": "Double",
        "fac_surface": "Double",
        "fac_highway": "Double",
        "fac_maxspeed": "Double",
        "fac_protection_level": "Double",
        "prot_level_separation_left": "Double",
        "prot_level_separation_right": "Double",
        "prot_level_buffer_left": "Double",
        "prot_level_buffer_right": "Double",
        "prot_level_left": "Double",
        "prot_level_right": "Double",
        "base_index": "Int",
        "fac_1": "Double",
        "fac_2": "Double",
        "fac_3": "Double",
        "fac_4": "Double",
        "data_bonus": "String",
        "data_malus": "String",
        "data_incompleteness": "Double",
        "data_missing": "String",
        "data_missing_width": "Int",
        "data_missing_surface": "Int",
        "data_missing_smoothness": "Int",
        "data_missing_maxspeed": "Int",
        "data_missing_parking": "Int",
        "data_missing_lit": "Int",
        "filter_usable": "Int",
        "filter_way_type": "String",
    }

# TODO: clean this up
def ensure_cycling_attribute_types(layer: QgsVectorLayer):
    with edit(layer):
        fields = layer.dataProvider().fields()
        for attr, ty in new_attributes_dict.items():
            attr_idx = fields.indexOf(attr)
            print('TODO', attr_idx)
            if ty == "Double":
                fields.at(attr_idx).setType(QVariant.Double)
            elif ty == "Int":
                print('TODO', attr)
                fields.at(attr_idx).setType(QVariant.Int)
        layer.updateFields()
    idx = layer.fields().indexOf('proc_maxspeed')
    print('TODO', layer.fields().at(idx).typeName(), layer.fields().at(idx).type() == QVariant.Int)
     
# TODO: don't use the in-out param "attributes_list"
def add_cyling_attributes(layer: QgsVectorLayer, attributes_list: list[str]) -> QgsVectorLayer:
    # list of new attributes, important for calculating cycling quality index
    
    # TODO: this is a weird "in-out" parameter
    for attr in list(new_attributes_dict.keys()):
        attributes_list.append(attr)

    # make sure all attributes are existing in the table to prevent errors when asking for a missing one
    with edit(layer):
        for attr in attributes_list:
            if layer.fields().indexOf(attr) == -1:
                if attr in new_attributes_dict:
                    if new_attributes_dict[attr] == "Double":
                        layer.dataProvider().addAttributes(
                            [QgsField(attr, QVariant.Double)]
                        )
                    elif new_attributes_dict[attr] == "Int":
                        layer.dataProvider().addAttributes(
                            [QgsField(attr, QVariant.Int)]
                        )
                    else:
                        layer.dataProvider().addAttributes(
                            [QgsField(attr, QVariant.String)]
                        )
                else:
                    layer.dataProvider().addAttributes(
                        [QgsField(attr, QVariant.String)]
                    )
        layer.updateFields()
    return layer


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
            # TODO: is this happening? How can this happen?
            if buffer_layer != road_layer:
                continue  # only consider geometries in the same layer
            road_id = road.attribute("id")
            road_highway = road.attribute("highway")
            road_name = road.attribute("name")
            road_maxspeed = d.getNumber(road.attribute("maxspeed"))
            # TODO: these lists are sets
            if road_id not in id_list:
                id_list.append(road_id)
            # TODO: these lists are sets
            if road_highway not in highway_list:
                highway_list.append(road_highway)
            # TODO: probably should be a method on a maxspeed_dict wrapper
            if (
                road_highway not in maxspeed_dict
                or maxspeed_dict[road_highway] < road_maxspeed
            ):
                maxspeed_dict[road_highway] = road_maxspeed
            # TODO: these lists are sets
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

@dataclass
class SidepathClassificationAttributes:
    id_proc_sidepath: int
    id_proc_highway: int
    id_proc_maxspeed: int


def sidepath_classification_attrs(layer:QgsVectorLayer) -> SidepathClassificationAttributes:
    id_proc_sidepath = layer.fields().indexOf("proc_sidepath")
    id_proc_highway = layer.fields().indexOf("proc_highway")
    id_proc_maxspeed = layer.fields().indexOf("proc_maxspeed")
    return SidepathClassificationAttributes(
           id_proc_sidepath=id_proc_sidepath,
           id_proc_highway=id_proc_highway,
           id_proc_maxspeed=id_proc_maxspeed
       )

def sidepath_classification(layer: QgsVectorLayer, sidepath_dict: dict, attrs: SidepathClassificationAttributes):
    # TODO: why is this not in "definitions" or "parameters"
    highway_class_list = [
        "motorway",
        "motorway_link",
        "trunk",
        "trunk_link",
        "primary",
        "primary_link",
        "secondary",
        "secondary_link",
        "tertiary",
        "tertiary_link",
        "unclassified",
        "residential",
        "road",
        "living_street",
        "service",
        "pedestrian",
        NULL,
    ]

    # a path is considered a sidepath if at least two thirds of its check points are found to be close to road segments with the same OSM ID, highway class or street name
    with edit(layer):
        for feature in layer.getFeatures():
            hw = feature.attribute("highway")
            maxspeed = feature.attribute("maxspeed")
            # TODO: this is redundant
            if maxspeed == "walk" or (not maxspeed and hw == "living_street"):
                maxspeed = 10
            if maxspeed == "none":
                maxspeed = 299
            if not maxspeed and hw == "living_street":
                maxspeed = 10
            if hw not in ["cycleway", "footway", "path", "bridleway", "steps"]:
                layer.changeAttributeValue(feature.id(), attrs.id_proc_highway, hw)
                layer.changeAttributeValue(
                    feature.id(), attrs.id_proc_maxspeed, d.getNumber(maxspeed)
                )
                continue
            id = feature.attribute("id")
            is_sidepath = feature.attribute("is_sidepath")
            if feature.attribute("footway") == "sidewalk":
                is_sidepath = "yes"
            is_sidepath_of = feature.attribute("is_sidepath:of")
            checks = sidepath_dict[id]["checks"]

            if not is_sidepath:
                is_sidepath = "no"

                for road_id in sidepath_dict[id]["id"].keys():
                    if checks <= 2:
                        if sidepath_dict[id]["id"][road_id] == checks:
                            is_sidepath = "yes"
                    else:
                        if sidepath_dict[id]["id"][road_id] >= checks * 0.66:
                            is_sidepath = "yes"

                if is_sidepath != "yes":
                    for highway in sidepath_dict[id]["highway"].keys():
                        if checks <= 2:
                            if sidepath_dict[id]["highway"][highway] == checks:
                                is_sidepath = "yes"
                        else:
                            if sidepath_dict[id]["highway"][highway] >= checks * 0.66:
                                is_sidepath = "yes"

                if is_sidepath != "yes":
                    for name in sidepath_dict[id]["name"].keys():
                        if checks <= 2:
                            if sidepath_dict[id]["name"][name] == checks:
                                is_sidepath = "yes"
                        else:
                            if sidepath_dict[id]["name"][name] >= checks * 0.66:
                                is_sidepath = "yes"

            layer.changeAttributeValue(feature.id(), attrs.id_proc_sidepath, is_sidepath)

            # derive the highway class of the associated road
            if not is_sidepath_of and is_sidepath == "yes":
                if len(sidepath_dict[id]["highway"]):
                    max_value = max(sidepath_dict[id]["highway"].values())
                    max_keys = [
                        key
                        for key, value in sidepath_dict[id]["highway"].items()
                        if value == max_value
                    ]
                    min_index = len(highway_class_list) - 1
                    for key in max_keys:
                        if highway_class_list.index(key) < min_index:
                            min_index = highway_class_list.index(key)
                    is_sidepath_of = highway_class_list[min_index]

            layer.changeAttributeValue(feature.id(), attrs.id_proc_highway, is_sidepath_of)

            if (
                is_sidepath == "yes"
                and is_sidepath_of
                and is_sidepath_of in sidepath_dict[id]["maxspeed"]
            ):
                maxspeed = sidepath_dict[id]["maxspeed"][is_sidepath_of]
                if maxspeed:
                    layer.changeAttributeValue(
                        feature.id(), attrs.id_proc_maxspeed, d.getNumber(maxspeed)
                    )
            # transfer names to sidepath
            if is_sidepath == "yes" and len(sidepath_dict[id]["name"]):
                name = max(
                    sidepath_dict[id]["name"],
                    key=lambda k: sidepath_dict[id]["name"][k],
                )  # the most frequent name in the surrounding
                if name:
                    layer.changeAttributeValue(
                        feature.id(), layer.fields().indexOf("name"), name
                    )

