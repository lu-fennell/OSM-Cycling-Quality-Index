# pyright: reportMissingModuleSource=false
from typing import TypeVar, cast
from qgis.core import (
    QgsVectorLayer,
    QgsProject
)

import os
import time
import json
import traceback
from dataclasses import dataclass  
from collections.abc import Callable  
from abc import ABC,abstractmethod  
from pathlib import Path

from cqi.featuredb import FeatureDb, FeatureSet
from cqi.featuredb_qgis import QgsFeatureSet
import cqi.lib as cqilib
from cqi.util import unwrap
import cqi.tracing as tracing
import tools.compare_traces as compare_traces


class Check(ABC):
    @abstractmethod
    def check(self, prj: 'TestProject') -> list[str]:
        raise NotImplementedError


CheckT = TypeVar('CheckT', bound=Check)

class TestProject:
    def __init__(self, project_dir: str, db: FeatureDb):
        self.project_dir = project_dir
        self.feature_db = db

    def out_dir(self) -> str:
        return f'{self.project_dir}/testoutput'

    def expected_dir(self) -> str:
        return  f'{self.project_dir}/traceoutput/original'        

    
    def input_file(self, name: str, ext: str) -> str:
        return f'{self.expected_dir()}/{name}.{ext}'


    def read_input_featureset(self, name: str) -> FeatureSet:
        return self.feature_db.import_geojson(self.input_file(name, 'geojson'))

    
    def read_input_layer(self, name: str) -> QgsVectorLayer:
        layer = cqilib.copy_to_mem_layer(cqilib.read_layer_geojson(self.input_file(name, 'geojson')))    
        unwrap(QgsProject.instance()).addMapLayer(layer, addToLegend=False)
        return layer

    # TODO: probably fix for qvariant
    def read_input_dict(self, name: str) -> dict:
        with open(self.input_file(name, 'json')) as f:
            result = json.load(f)
        return result

    def run_checks(self, checks: list[CheckT]):
        os.makedirs(self.out_dir(), exist_ok=True)
        for f in os.listdir(self.out_dir()):
            # TODO: improve cleanup
            if f.endswith('.json') or f.endswith('geojson'):
                os.remove(Path(self.out_dir()) / f)
    
        failed_count = 0
        # TODO: print runtime of tests
        for idx, check in enumerate(checks):
            print(f'[{idx}] {check}... ', end='', flush=True)
            start = time.perf_counter()
            try:
                errors = check.check(self)
                if errors:
                    print_run_result(start, f'FAILED\n  {'\n  '.join(errors)}')
                    failed_count += 1
                else:
                    print_run_result(start, 'OK')
            except Exception as e:
                print_run_result(start, f'ERROR: {e.__class__} {e}')
                traceback.print_exc()
                failed_count += 1


        if failed_count == 0:
            print(f'All {len(checks)} test cases OK')
        else:
            print(f'{failed_count} of {len(checks)} test cases FAILED')



@dataclass
class LayerCheck(Check):
    fun: Callable[[QgsVectorLayer], QgsVectorLayer]
    input: str
    expected: str

    def check(self, prj: TestProject) -> list[str]: 
        input_layer = prj.read_input_layer(self.input)
        output_layer = self.fun(input_layer)
        out_file = tracing.write_layer(prj.out_dir(), self.expected, output_layer)
        return compare_traces.compare_geojson(out_file, prj.input_file(self.expected, 'geojson'))

@dataclass
class LayerCheck2(Check):
    fun: Callable[[FeatureSet, dict], None]
    input1: str
    input2: str
    expected: str

    def check(self, prj: TestProject) -> list[str]: 
        input_features = prj.read_input_featureset(self.input1)
        d = prj.read_input_dict(self.input2)
        self.fun(input_features, d)
        output_layer = cast(QgsFeatureSet, input_features).to_layer()
        out_file = tracing.write_layer(prj.out_dir(), self.expected, output_layer)
        return compare_traces.compare_geojson(out_file, prj.input_file(self.expected, 'geojson'))

@dataclass
class DictCheck(Check):
    fun: Callable[[FeatureSet], dict]
    input1: str
    expected: str

    # TODO: measure time only for "fun"
    def check(self, prj: TestProject) -> list[str]:
        input_features = prj.read_input_featureset(self.input1)
        output = self.fun(input_features)
        out_file = tracing.write_dict(prj.out_dir(), self.expected, output)
        return compare_traces.compare_json(out_file, prj.input_file(self.expected, 'json'))

@dataclass
class DictCheck2(Check):
    fun: Callable[[QgsVectorLayer, QgsVectorLayer], dict]
    input1: str
    input2: str
    expected: str

    # TODO: measure time only for "fun"
    def check(self, prj: TestProject) -> list[str]:
        input_layer1 = prj.read_input_layer(self.input1)
        input_layer2 = prj.read_input_layer(self.input2)
        output = self.fun(input_layer1, input_layer2)
        out_file = tracing.write_dict(prj.out_dir(), self.expected, output)
        return compare_traces.compare_json(out_file, prj.input_file(self.expected, 'json'))

# TODO: extract to a test_lib module
def print_run_result(start_time: float, msg: str):
    elapsed = time.perf_counter() - start_time
    print(f'{msg}\n  Elapsed: {elapsed}s)')

