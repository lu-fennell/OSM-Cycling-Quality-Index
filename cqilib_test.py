from typing import assert_type, cast
from console.console import _console  # type: ignore[import-not-found]
import os
import sys

from cqi.featuredb import FeatureSet
import reload_local_modules
import cqi.lib as cqilib
from cqi.util import unwrap
from cqi.testlib import DictCheck, TestProject, Check, LayerCheck, LayerCheck2, DictCheck2
import parameter as p
from cqi.featuredb_qgis import QgsFeatureDb, QgsFeatureSet
from qgis.core import QgsVectorLayer, QgsProject

# TODO: Find a better way to determine the project dir.. maybe through the Qgis project home for now
project_dir = os.path.dirname(
    _console.console.tabEditorWidget.currentWidget()._editor_code_widget.filePath()
)

reload_local_modules.reload(project_dir)

# TODO: clean this up
def sidepath_classification_testwrapper(feature_set: FeatureSet, sidepath_dict: dict):
    cqilib.add_cyling_attributes(feature_set, p.attributes_list)
    # sidepath_dict = cqilib.sidepath_dict(feature_set)
    cqilib.sidepath_classification(feature_set, sidepath_dict, cqilib.attribute_ids(cast(QgsFeatureSet, feature_set).to_layer()))


checks = [
    # TODO: the following three are obsolete
    # LayerCheck(cqilib.sidepath_create_layer_path, '03_with_extended_attributes', '04_extracted_layer_path'),
    # LayerCheck(cqilib.sidepath_create_layer_roads, '03_with_extended_attributes', '05_extracted_layer_roads'),
      
    DictCheck(cqilib.sidepath_dict, '03_with_extended_attributes', '04_sidepath_dict'),
    LayerCheck2(sidepath_classification_testwrapper, '02_reduced_fields', '04_sidepath_dict', '05_sidepaths'),
]



TestProject(project_dir, QgsFeatureDb(unwrap(QgsProject.instance()))).run_checks(checks)



