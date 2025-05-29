from console.console import _console  # type: ignore[import-not-found]
import os
import sys

import reload_local_modules
import cqi.lib as cqilib
from cqi.testlib import TestProject, Check, LayerCheck, LayerCheck2, DictCheck2
import parameter as p
from cqi.featuredb_qgis import QgsFeatureDb, QgsFeatureSet
from qgis.core import QgsVectorLayer, QgsProject

# TODO: Find a better way to determine the project dir.. maybe through the Qgis project home for now
project_dir = os.path.dirname(
    _console.console.tabEditorWidget.currentWidget()._editor_code_widget.filePath()
)

reload_local_modules.reload(project_dir)


# TODO: clean this up
def sidepath_classification_testwrapper(layer: QgsVectorLayer, sidepath_dict: dict) -> QgsVectorLayer:
    # TODO: add_cyling_attributes is a proc!
    db = QgsFeatureDb(QgsProject.instance())
    feature_set = db.import_layer(layer)
    cqilib.add_cyling_attributes(feature_set, p.attributes_list)
    layer = feature_set.to_layer()
    sidepath_dict = cqilib.sidepath_dict(layer)
    cqilib.sidepath_classification(layer, sidepath_dict, cqilib.attribute_ids(layer))
    return layer

checks : list[Check] = [
    # TODO: the following three are obsolete
    # LayerCheck(cqilib.sidepath_create_layer_path, '03_with_extended_attributes', '04_extracted_layer_path'),
    # LayerCheck(cqilib.sidepath_create_layer_roads, '03_with_extended_attributes', '05_extracted_layer_roads'),
    # DictCheck2(cqilib.sidepath_dict, '09_layer_path_points_buffer', '05_extracted_layer_roads', '10_sidepath_dict'),
    # TODO: why is the return type of functions not typechecked?
    LayerCheck2(sidepath_classification_testwrapper, '02_reduced_fields', '04_sidepath_dict', '05_sidepaths'),
]


TestProject(project_dir).run_checks(checks)



