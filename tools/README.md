Tools related to the Cycling-Quality-Index (CQI) but not dependent on QGIS.

# Prerequisites

The tools are intended to be run from the repository root using [poetry](https://python-poetry.org/). Other virtual-environment-managers that understand a `pyproject.toml` file may work as well but haven't been tested.

Before running the tools, install the required dependencies:

```
$ poetry lock
[...]
$ poetry install --no-root
```

Then run a tool with

```
$ poetry run python tools/<tool>.py
```

See also the examples below.


# cqi_postgis.py

PostGIS-based calculation of the `sidepath_dict`.

The `sidepath_dict` contains all information to calculate the CQI for each path locally (i.e., by just looking at the tags of a way, without relating it to other ways in the neighborhood)

The script has two commands, `import` and `generate-sidepath-dict`.

## Command: import

```
usage: cqi_postgis.py import [-h] [--filter FILTER_JSON_FILE] GEOJSON_FILE TABLE_NAME

import geojson file into postgis

positional arguments:
  GEOJSON_FILE
  TABLE_NAME

options:
  -h, --help            show this help message and exit
  --filter FILTER_JSON_FILE
```

Import a geojson file into a PostGIS database as a table that is compatible for the `generate-sidepath-dict` command.

- The connection to a PostGIS-DB has to be given with the environment variable `GEO_DATABASE_URL`, as a postgres-URL
- `GEOJSON_FILE` a geojson file containing all the roads and paths of interest for `sidepath_dict` generation
- `TABLE_NAME` the name of the table to import the way-data into. It will be created if it does not exist. It will be cleared if it exists.
- `--filter` expects a json file with some filter rules. The two provided filter files `../roads-filter.json` and `../paths-filter.json` will filter a "complete" geojson of an area (like `../data/way_import.geojson`) to the set of "roads", resp. "paths", that the `sidepath_dict` calculation expects.

Example run (from repository root):

```
$ export GEO_DATABASE_URL=postgres://postgres:postgres@127.0.0.1/postgres
$ poetry run python tools/cqi_postgis.py import --filter roads-filter.json data/way_import.geojson way_import_roads
$ poetry run python tools/cqi_postgis.py import --filter paths-filter.json data/way_import.geojson way_import_paths
```

## Command: generate-sidepath-dict

```
usage: cqi_postgis.py generate-sidepath-dict [-h] [--format {jsonl,json}] ROADS_TABLE_NAME PATHS_TABLE_NAME

generate sidepath dict from roads and paths

positional arguments:
  ROADS_TABLE_NAME
  PATHS_TABLE_NAME

options:
  -h, --help            show this help message and exit
  --format {jsonl,json}
```

- The connection to a PostGIS-DB has to be given with the environment variable `GEO_DATABASE_URL`, as a postgres-URL
- `ROADS_TABLE_NAME` is the name of the table containing the relevant "roads" (cf import command and `../roads-filter.json`)
- `PATHS_TABLE_NAME` is the name of the table containing the relevant "paths" (cf import command and `../paths-filter.json`) 
- Running the command prints the `sidepath_dict` information to stdout as newline-seperated-JSON (or just JSON, cf `--format` option)

Example run (from repository root):

```
$ export GEO_DATABASE_URL=postgres://postgres:postgres@127.0.0.1/postgres
$ poetry run python tools/cqi_postgis.py generate-sidepath-dict way_import_roads way_import_paths > sidepath_dict.jsonl
```

