import sys
import json
import argparse
import os
from enum import Enum
from dataclasses import dataclass  # noqa: F401


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


def read_json(fname: str) -> dict:
    with open(fname) as f:
        result = json.load(f)
    return result

@dataclass
class Feature:
    id: str
    properties: dict
    geometry: dict

def feature_from_dict(d: dict) -> Feature:
    properties = d['properties']
    geometry = d['geometry']
    id = properties['id']
    return Feature(id, properties, geometry)

# TODO: compare meta
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
            errors.append(f'First difference at idx {idx}: {feature1.id} , {feature2.id}')
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
    for key in common_keys:
        if json1[key] != json2[key]:
            errors.append(f'difference at common key {key}')
    return errors

def compare_files(f1: str, f2: str) -> list[str]:
    match (input_file_type(f1), input_file_type(f2)):
        case (InputFileType.GEOJSON, InputFileType.GEOJSON):
            return compare_geojson(f1, f2)
        case (InputFileType.JSON, InputFileType.JSON):
            return compare_json(f1, f2)
        case (t1, t2):
            warn(f'Comparison not implemented: {f1}:{t1} and {f2}:{t2}')
            return []
        case _:
            raise Exception('unreachable')

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


parser = argparse.ArgumentParser(description='compare two directories with json/geojson files or two json/geojson files for equality')
parser.add_argument('f1', metavar='FILE_OR_DIRECTORY')
parser.add_argument('f2', metavar='FILE_OR_DIRECTORY', nargs='?')
args = parser.parse_args()

class InputFileType(Enum):
    GEOJSON = 1
    JSON = 2
    DIR = 3

def input_file_type(f: str) -> InputFileType:
    if f.endswith('.geojson'):
        return InputFileType.GEOJSON
    elif f.endswith('.json'):
        return InputFileType.JSON
    else:
        # TODO: maybe check that this is a dir?
        return InputFileType.DIR

if args.f2 is None and input_file_type(args.f1) == InputFileType.DIR:
    compare_changes(args.f1)
else:
    t1 = input_file_type(args.f1)
    t2 = input_file_type(args.f2)
    if t1 != t2:
        raise Exception(f'Incompatible input files {t1} and {t2}. Both files have to be the same type')

    if t1 == InputFileType.GEOJSON:
        errors = compare_geojson(args.f1, args.f2)
    elif t1 == InputFileType.JSON:
        errors = compare_json(args.f1, args.f2)
    elif t1 == InputFileType.DIR:
        errors = compare_dirs(args.f1, args.f2)
    else:
        raise Exception(f'Input file type {t1} not yet implemented')



    if not errors:
        print("SAME")
    else:
        print("DIFFERENT")
        for e in errors:
            print(f'* {e}')
        sys.exit(-1)







