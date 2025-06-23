import sys
import json
import argparse
import os
import math
from enum import Enum
from dataclasses import dataclass  # noqa: F401
from typing import TextIO, Tuple

# TODO: this should be a parameter or cmd line argument
#
sidepath_diff_output_file = 'tmp/sidepath_dict_diffs.json'

class Color(Enum):
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    BOLD = '\033[1m'    

def colorize(s: str, color: Color) -> str:
    return f'{color.value}{s}{Color.RESET.value}'

def warn(msg: str):
    print(f'{colorize('WARNING', Color.YELLOW)}: {msg}')

def info(msg: str):
    print(f'{colorize('INFO', Color.BOLD)}: {msg}')

def info_nonl(msg: str):
    print(f'{colorize('INFO', Color.BOLD)}: {msg}', end = '', flush = True)

def read_jsonl(fname: str) -> dict:
    result = {}
    with open(fname) as f:
        for l in f:
            l_array = json.loads(l)
            result[l_array[0]] = {
                'checks': l_array[1],
                'id': l_array[2],
                'highway': l_array[3],
                'name': l_array[4],
                'maxspeed': l_array[5]
            }
    return result

def read_json(fname: str) -> dict:
    if fname.endswith('jsonl'):
        return read_jsonl(fname)
    else:
        with open(fname) as f:
            result = json.load(f)
        return result

def similar_coordinates(tol: float, c1: list[list[float]], c2: list[list[float]]) -> bool:
    return (len(c1) == len(c2) and all([ math.isclose(n1, n2, abs_tol=tol) for ns1, ns2 in zip(c1, c2) for n1, n2 in zip(ns1, ns2) ]))

def similar_geometry(tolerance: float, g1: dict, g2: dict) -> bool:
    return g1 == g2 or (g1['type'] == g2['type'] and similar_coordinates(tolerance, g1['coordinates'], g2['coordinates']))

@dataclass
class Feature:
    id: str
    properties: dict
    geometry: dict

    def __eq__(self, other):
        return isinstance(other, Feature) and self._similar(other)

    def _similar(self, other: 'Feature') -> bool:
        return self.id == other.id and self.properties == other.properties and similar_geometry(1e-9, self.geometry, other.geometry)

def feature_from_dict(d: dict) -> Feature:
    properties = d['properties']
    geometry = d['geometry']
    id = properties['id']
    return Feature(id, properties, geometry)

def get_features(d: dict) -> list[Feature]:
    return [feature_from_dict(v) for v in d['features']]

def compare_geojson(f1: str, f2:str) -> list[str]:
    features1 = get_features(read_json(f1))
    features2 = get_features(read_json(f2))

    errors = []


    def feature_id(d: dict) -> str:
        return d['properties']['id']

    if features1 != features2:
        errors.append("Features are different")

    if len(features1) != len(features2):
        errors.append(f'Feature count differs: {len(features1)} <> {len(features2)}')
        if len(features1) < len(features2):
            errors.append(f'First additional feature id right: {features2[len(features1)].id}')
        if len(features1) > len(features2):
            errors.append(f'First additional feature id left: {features1[len(features2)].id}')
        

    for idx, feature1 in enumerate(features1[0:len(features2)]):
        feature2 = features2[idx]
        if feature1 != feature2:
            # TODO: clean this up, improve
            first_diff_prop = None
            for pk1, pv1 in feature1.properties.items():
                if pk1 in feature2.properties.keys():
                    pv2 = feature2.properties[pk1]
                    if pv1 != pv2:
                        first_diff_prop = (pk1, pv1, pv2)
                        break
                else:
                    first_diff_prop = (pk1, pv1, "<not found>")
            errors.append(f'First difference at idx {idx}: {feature1.id} , {feature2.id}, props-eq? {feature1.properties == feature2.properties}, {first_diff_prop}')
            break
    return errors

def compare_json(f1: str, f2: str) -> list[str]:
    errors = []

    json1 = read_json(f1)
    json2 = read_json(f2)

    keys1 = set(json1.keys())
    keys2 = set(json2.keys())

    if keys1 != keys2:
        only1 = sorted(keys1 - keys2)
        only2 = sorted(keys2 - keys1)
        errors.append(f'keys differ\n  only left: {only1}\n  only right: {only2}')

    common_keys = keys1.intersection(keys2)
    diff_output : dict = {}
    for key in common_keys:
        v1 = json1[key]
        v2 = json2[key]
        if v1 != v2:
            errors.append(f'difference at common key {key}')
            if _is_sidepath_dict(v1) and _is_sidepath_dict(v2):
                sidepath_dict_errors, d = compare_sidepath_dicts(v1, v2)
                errors += sidepath_dict_errors
                if d is not None:
                    diff_output[key] = d
            else:
                errors.append(f'  {json.dumps(v1)}')
                errors.append(f'  {json.dumps(v2)}')
    # TODO: would be much better to pass the file as an argument
    #    or rather defer displaying of errors and have multiple output formats (text, json-file, etc)
    try: 
        with open(sidepath_diff_output_file, "w") as f:
            json.dump(diff_output, f, indent=2)
    except FileNotFoundError as e:
        print(f"WARNING: could not write sidepath_diff_output: {e}")
    return errors

def _is_sidepath_dict(v) -> bool:
    sidepath_keys = { 'checks', 'id', 'highway', 'name', 'maxspeed' }
    if isinstance(v, dict):
        return 'checks' in v and v.keys() == sidepath_keys
    else:
        return False

def compare_sidepath_dicts(d1: dict, d2:dict) -> Tuple[list[str], dict | None]:
    errors: list[str] = [] 
    id_diffs = None
    if d1 != d2:
        diffs = { k: (v1, d2.get(k)) for k, v1 in d1.items() if d2.get(k) != v1}
        for k, (v1, v2) in diffs.items():
            errors.append(f'  {k}:')
            errors.append(f'    {display_sorted(v1)}')
            errors.append(f'    {display_sorted(v2)}')
            if k == 'id':
                id_diffs = { 'v1': v1, 'v2': v2}
    return (errors, id_diffs)

def display_sorted(v) -> str:
    if isinstance(v, dict):
        return str(sorted(v.items()))
    else:
        return str(v)

def compare_files(f1: str, f2: str) -> list[str]:
    match (input_file_type(f1), input_file_type(f2)):
        case (InputFileType.GEOJSON, InputFileType.GEOJSON):
            return compare_geojson(f1, f2)
        case (InputFileType.JSON, InputFileType.JSON):
            return compare_json(f1, f2)
        case (t1, t2):
            warn(f'Comparison not implemented: {f1}:{t1} and {f2}:{t2}')
            return []

def compare_dirs(d1: str, d2: str) -> list[str]:
    names1 = set(os.listdir(d1))
    names2 = set(os.listdir(d2))
    errors = []
    if names1 != names2:
        only1 = sorted(names1 - names2)
        only2 = sorted(names2 - names1)
        errors.append(f'files differ:\n  only left: {only1}\n  only right: {only2}')
    common_names = sorted(names1.intersection(names2))
    for name in common_names:
        info_nonl(f'Comparing {name}')
        file_errors = compare_files(f'{d1}/{name}', f'{d2}/{name}')
        print(f': {colorize('SAME', Color.GREEN) if not file_errors else colorize('DIFF', Color.RED)}')
        errors += [ f'{name}: {e}' for e in file_errors] 

    return errors

def compare_changes(d: str) -> list[str]:
    names1 = sorted(os.listdir(d))
    names2 = sorted(os.listdir(d))[1:]
    errors = []
    for (n1, n2) in zip(names1, names2):
        info_nonl(f'Checking changes {n1} -> {n2}')
        f1 = f'{d}/{n1}'
        f2 = f'{d}/{n2}'
        if input_file_type(f1) != input_file_type(f2):
              print(':', colorize('OK', Color.GREEN))
        else:
            file_errors = compare_files(f1, f2)
            if not file_errors:
                print(':', colorize('NO CHANGE', Color.RED))
                errors.append(f'No change from {n1} -> {n2}')
            else:
              print(':', colorize('OK', Color.GREEN))
    return errors

class InputFileType(Enum):
    GEOJSON = 1
    JSON = 2
    DIR = 3

def input_file_type(f: str) -> InputFileType:
    if f.endswith('.geojson'):
        return InputFileType.GEOJSON
    elif f.endswith('.json') or f.endswith('.jsonl'):
        return InputFileType.JSON
    else:
        # TODO: maybe check that this is a dir?
        return InputFileType.DIR

def run(f1: str, f2: str | None) -> bool:
    if f2 is None and input_file_type(f1) == InputFileType.DIR:
        errors = compare_changes(f1)
        return not errors
    elif f2 is not None:
        t1 = input_file_type(f1)
        t2 = input_file_type(f2)
        if t1 != t2:
            raise Exception(f'Incompatible input files {t1} and {t2}. Both files have to be the same type')

        if t1 == InputFileType.GEOJSON:
            errors = compare_geojson(f1, f2)
        elif t1 == InputFileType.JSON:
            errors = compare_json(f1, f2)
        elif t1 == InputFileType.DIR:
            errors = compare_dirs(f1, f2)
        else:
            raise Exception(f'Input file type {t1} not yet implemented')
        if not errors:
            print("SAME")
            return True
        else:
            print("DIFFERENT")
            for e in errors:
                print(f'* {e}')
            return False
    else:
        raise Exception(f'{f1} is not a directory and only one file is provided. This combination of arguments is not supported')
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='compare two directories with json/geojson files or two json/geojson files for equality')
    parser.add_argument('f1', metavar='FILE_OR_DIRECTORY')
    parser.add_argument('f2', metavar='FILE_OR_DIRECTORY', nargs='?')
    args = parser.parse_args()
    if not run(args.f1, args.f2):
        sys.exit(-1)








