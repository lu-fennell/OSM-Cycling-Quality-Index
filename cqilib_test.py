from qgis.core import NULL, edit  # type: ignore[attr-defined]

from qgis.core import (
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsProject
)

import os
import time
from console.console import _console  # type: ignore[import-not-found]
import importlib

import cqilib
importlib.reload(cqilib)
from dataclasses import dataclass  
from collections.abc import Callable  
from abc import ABC,abstractmethod  
import tracing  
importlib.reload(tracing)
import compare_traces  
importlib.reload(compare_traces)

# TODO: Find a better way to determine the project dir.. maybe through the Qgis project home for now
project_dir = os.path.dirname(
    _console.console.tabEditorWidget.currentWidget()._editor_code_widget.filePath()
)

out_dir = f'{project_dir}/testoutput'
expected_dir = f'{project_dir}/traceoutput/original'
os.makedirs(out_dir, exist_ok=True)

def input_file(name: str, ext: str) -> str:
    return f'{expected_dir}/{name}.{ext}'

def read_input_layer(name: str) -> QgsVectorLayer:
    layer = cqilib.copy_to_mem_layer(cqilib.read_layer_geojson(input_file(name, 'geojson')))    
    QgsProject.instance().addMapLayer(layer, addToLegend=False)
    return layer

class Check(ABC):
    @abstractmethod
    def check(self) -> list[str]:
        raise NotImplementedError

@dataclass
class LayerCheck(Check):
    fun: Callable[[QgsVectorLayer], QgsVectorLayer]
    input: str
    expected: str

    def check(self) -> list[str]: 
        input_layer = read_input_layer(self.input)
        output_layer = self.fun(input_layer)
        out_file = tracing.write_layer(out_dir, self.expected, output_layer)
        return compare_traces.compare_geojson(out_file, input_file(self.expected, 'geojson'))

@dataclass
class DictCheck2(Check):
    fun: Callable[[QgsVectorLayer, QgsVectorLayer], dict]
    input1: str
    input2: str
    expected: str

    # TODO: measure time only for "fun"
    def check(self) -> list[str]:
        input_layer1 = read_input_layer(self.input1)
        input_layer2 = read_input_layer(self.input2)
        output = self.fun(input_layer1, input_layer2)
        out_file = tracing.write_dict(out_dir, self.expected, output)
        return compare_traces.compare_json(out_file, input_file(self.expected, 'json'))


checks = [
    LayerCheck(cqilib.sidepath_create_layer_path, '03_with_extended_attributes', '04_extracted_layer_path'),
    LayerCheck(cqilib.sidepath_create_layer_roads, '03_with_extended_attributes', '05_extracted_layer_roads'),
    DictCheck2(cqilib.sidepath_dict, '09_layer_path_points_buffer', '05_extracted_layer_roads', '10_sidepath_dict'),
]

# TODO: extract to a test_lib module
def print_run_result(start_time: float, msg: str):
    elapsed = time.perf_counter() - start_time
    print(f'{msg}\n  Elapsed: {elapsed}s)')

failed_count = 0
# TODO: print runtime of tests
for idx, check in enumerate(checks):
    print(f'[{idx}] {check}... ', end='', flush=True)
    start = time.perf_counter()
    try:
        errors = check.check()
        if errors:
            print_run_result(start, f'FAILED\n  {'\n  '.join(errors)}')
            failed_count += 1
        else:
            print_run_result(start, 'OK')
    except Exception as e:
        print_run_result(start, f'ERROR: {e.__class__} {e}')
        failed_count += 1


if failed_count == 0:
    print(f'All {len(checks)} test cases OK')
else:
    print(f'{failed_count} of {len(checks)} test cases FAILED')





