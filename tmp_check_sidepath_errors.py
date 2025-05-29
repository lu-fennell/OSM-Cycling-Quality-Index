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

import reload_local_modules
import cqilib
import sys
import os
import json
from typing import Tuple


index = 0

def expressions(path_id: str, diff: dict) -> Tuple[str, str, str]:
    v1 = roads_expression(diff['v1'])
    v2 = roads_expression(diff['v2'])
    return (id_expression(path_id), v1, v2)

def id_expression(id: str) -> str:
    return f'{key("id")} IS {val(id)}'

def roads_expression(d: dict) -> str:
    ids = [id_expression(id)  for id in d.keys() ]
    return " OR ".join(ids)

def key(s: str) -> str:
    return '"' +  s + '"'
def val(s: str) -> str:
    return "'" + s + "'"


prj =  QgsProject.instance()
prj_dir = f'{prj.absolutePath()}/OSM-Cycling-Quality-Index/'

reload_local_modules.reload(prj_dir)

with open(f'{prj_dir}/sidepath_dict_diffs.json') as f:
    diffs = json.load(f)
    diff_indices = sorted(diffs.keys())

import_style_path = f'{prj_dir}/styles/import.qml'
sidepath_style_path = f'{prj_dir}/styles/path.qml'
original_style_path = f'{prj_dir}/styles/original.qml'
postgis_style_path = f'{prj_dir}/styles/postgis.qml'

way_import_file = f'{prj_dir}/data/way_import.geojson'



def load_layer(way_import: QgsVectorLayer, expression: str, name: str, style_path: str) -> QgsVectorLayer:
    layer =  cqilib.process_to_mem_layer(
        "native:extractbyexpression",
        {"INPUT": way_import, "EXPRESSION": expression, "OUTPUT": "memory:"},
    )
    layer.setName(name)
    layer.loadNamedStyle(style_path)
    prj.addMapLayer(layer, True)
    return layer

def run_next_diff():
    global index
    if index >= len(diff_indices):
        print('NO MORE DIFFERENCES')

    prj.removeAllMapLayers()
    # TODO: reproject as in cycling_quality_index
    way_import = cqilib.read_layer_geojson(way_import_file, name='way_import', filter='geometrytype=LineString')
    way_import.loadNamedStyle(import_style_path)
    prj.addMapLayer(way_import, True)

    # TODO: make sure 'postgis' and 'original' cannot be confused
    path_id = diff_indices[index]
    diff = diffs[path_id]
    id_e, v1_e, v2_e = expressions(path_id, diff)
    load_layer(way_import, id_e, 'sidepath', sidepath_style_path)
    postgis_layer = load_layer(way_import, v1_e, 'postgis', postgis_style_path)
    load_layer(way_import, v2_e, 'original', original_style_path)

    canvas = iface.mapCanvas()
    canvas.setExtent(postgis_layer.extent())
    canvas.refresh()
    index += 1

run_next_diff()




