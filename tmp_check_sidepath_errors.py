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

diff = json.loads("""
   {"way/1070140394": {
        "v1": {"way/936928425": 1, "way/1218719809": 1, "way/1218719810": 1, "way/1313692353": 1, "way/1079762775": 1, "way/1313692335": 2, "way/548693222": 1, "way/1079762778": 1, "way/1218723794": 1},
        "v2": {"way/1218719809": 1, "way/1313692353": 1, "way/936928425": 1, "way/1218719810": 1, "way/1313692335": 2, "way/1079762775": 1, "way/1079762778": 1, "way/1218723794": 1}
        }
    }
""")

def expressions(diff: dict) -> Tuple[str, str, str]:
    id = next(diff.keys().__iter__())
    v1 = roads_expression(diff[id]['v1'])
    v2 = roads_expression(diff[id]['v2'])
    return (id_expression(id), v1, v2)

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

prj.removeAllMapLayers()
import_style_path = f'{prj_dir}/styles/import.qml'
sidepath_style_path = f'{prj_dir}/styles/path.qml'
original_style_path = f'{prj_dir}/styles/original.qml'
postgis_style_path = f'{prj_dir}/styles/postgis.qml'

way_import_file = f'{prj_dir}/data/way_import.geojson'

way_import = cqilib.read_layer_geojson(way_import_file, name='way_import', filter='geometrytype=LineString')
way_import.loadNamedStyle(import_style_path)
prj.addMapLayer(way_import, True)


def load_layer(expression: str, name: str, style_path: str) -> QgsVectorLayer:
    layer =  cqilib.process_to_mem_layer(
        "native:extractbyexpression",
        {"INPUT": way_import, "EXPRESSION": expression, "OUTPUT": "memory:"},
    )
    layer.setName(name)
    layer.loadNamedStyle(style_path)
    prj.addMapLayer(layer, True)
    return layer

# TODO: make sure 'postgis' and 'original' cannot be confused
id_e, v1_e, v2_e = expressions(diff)
load_layer(id_e, 'sidepath', sidepath_style_path)

postgis_layer = load_layer(v1_e, 'postgis', postgis_style_path)
load_layer(v2_e, 'original', original_style_path)

canvas = iface.mapCanvas()
canvas.setExtent(postgis_layer.extent())
canvas.refresh()



