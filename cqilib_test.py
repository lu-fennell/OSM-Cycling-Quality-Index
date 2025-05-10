from console.console import _console  # type: ignore[import-not-found]
import importlib
import os

import cqilib
importlib.reload(cqilib)
import cqi_testlib
importlib.reload(cqi_testlib)
from cqi_testlib import LayerCheck, DictCheck2, TestProject

checks = [
    LayerCheck(cqilib.sidepath_create_layer_path, '03_with_extended_attributes', '04_extracted_layer_path'),
    LayerCheck(cqilib.sidepath_create_layer_roads, '03_with_extended_attributes', '05_extracted_layer_roads'),
    DictCheck2(cqilib.sidepath_dict, '09_layer_path_points_buffer', '05_extracted_layer_roads', '10_sidepath_dict'),
]

# TODO: Find a better way to determine the project dir.. maybe through the Qgis project home for now
project_dir = os.path.dirname(
    _console.console.tabEditorWidget.currentWidget()._editor_code_widget.filePath()
)

TestProject(project_dir).run_checks(checks)



