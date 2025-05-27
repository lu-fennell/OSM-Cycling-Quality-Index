import psycopg
import argparse
import json
from dataclasses import dataclass
from enum import Enum
import sys
import csv
from typing import Tuple

@dataclass
class Row:
    buffer_id: str
    buffer_nr: int
    buffer_layer: str
    road_id: str
    road_layer: str
    road_highway: str
    road_name: str
    maxspeed: str

@dataclass
class SidepathEntryResult:
    count: int
    road_ids: dict[str, int]
    highways: dict[str, int]
    names: dict[str, int]
    maxspeed: dict[str, float]

@dataclass
class SidepathEntry:
    nrs: set[int]
    road_ids: dict[str, set[int]]
    highways: dict[str, set[int]]
    names: dict[str, set[int]]
    maxspeed: dict[str, float]

    def __init__(self):
        self.nrs = set()
        self.road_ids = {}
        self.highways = {}
        self.names = {}
        self.maxspeed = {}

    def add_row(self, r: Row):
        self.nrs.add(r.buffer_nr)
        if r.buffer_layer == r.road_layer:
            _add_entry(self.road_ids, r.road_id, r.buffer_nr )
            _add_entry(self.highways, r.road_highway, r.buffer_nr)
            _add_entry(self.names, r.road_name, r.buffer_nr)
            _max_entry(self.maxspeed, r.road_highway, _float_or_none(r.maxspeed))

    def result(self) -> SidepathEntryResult:
        return SidepathEntryResult(
            count=len(self.nrs),
            road_ids=_histogram(self.road_ids),
            highways=_histogram(self.highways),
            names=_histogram(self.names),
            maxspeed=self.maxspeed
        )

def _add_entry(d: dict[str, set[int]], key: str, nr: int):
    if key is not None:
        d.setdefault(key, set()).add(nr)

def _max_entry(d: dict[str, float], key: str, v: float | None):
    if key is not None and v is not None:
        d.setdefault(key, 0.0)
        d[key] = max(v, d[key])

def _histogram(d: dict[str, set[int]]) -> dict[str, int]:
    return { k: len(v) for k, v in d.items() }

class SidepathDictStream:
    def __enter__(self) -> 'SidepathDictStream':
        return self
    def __exit__(self, _ty, _val, _trace):
        return False
    def write_entry(self, buffer_id, sidepath_entry):
        print(json.dumps([
          buffer_id,
          sidepath_entry.count,
          sidepath_entry.road_ids,
          sidepath_entry.highways,
          sidepath_entry.names,
          sidepath_entry.maxspeed,
        ]))

class SidepathDictObj:
    def __init__(self):
        self.obj = {}
    def __enter__(self) -> 'SidepathDictObj':
        return self
    def __exit__(self, _ty, _val, _trace):
        print(json.dumps(self.obj, indent=2))
        return False
    def write_entry(self, buffer_id: str, sidepath_entry: SidepathEntryResult):
        self.obj[buffer_id] = {
            'checks': sidepath_entry.count,
            'id': sidepath_entry.road_ids,
            'highway': sidepath_entry.highways,
            'name': sidepath_entry.names,
            'maxspeed': sidepath_entry.maxspeed
        }

def sidepath_dict_writer(stream: bool) -> SidepathDictObj | SidepathDictStream:
    if stream:
        return SidepathDictStream()
    else:
        return SidepathDictObj()


def _float_or_none(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s)
    except ValueError:
        return None



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="calculate cqi on postgis")
    parser.add_argument("roads_table", metavar="ROADS_TABLE_NAME")
    parser.add_argument("paths_table", metavar="PATHS_TABLE_NAME")
    parser.add_argument("--format", default='jsonl', required=False, choices=['jsonl', 'json'])
    args = parser.parse_args()

    roads_table = psycopg.sql.Identifier(args.roads_table)
    paths_table = psycopg.sql.Identifier(args.paths_table)

    with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres") as conn:
        with conn.cursor(name = 'cqi_sidepath_dict', row_factory = psycopg.rows.dict_row) as cur:
            conn.execute("CREATE TEMPORARY SEQUENCE buffer_nr_sequence;")
            query = psycopg.sql.SQL("""
                WITH 
                points AS (
                    SELECT id, nextval('buffer_nr_sequence') AS nr, tags -> 'tags' -> 'layer' as layer, (ST_Dump(
                                    ST_Union(
                                        CASE WHEN ST_Length(geom) >= %(buffer_distance)s 
                                        THEN ARRAY[
                                                ST_Startpoint(geom), 
                                                ST_Endpoint(geom), 
                                                ST_Lineinterpolatepoints(geom, %(buffer_distance)s/st_length(geom))
                                            ]
                                        ELSE ARRAY[
                                                ST_Startpoint(geom), 
                                                ST_Endpoint(geom)
                                            ]
                                        END
                                    )
                                )).geom
                    FROM {paths_table}
                    ORDER BY id
                )
                SELECT 
                    points.id AS buffer_id, 
                    points.nr AS buffer_nr,
                    points.layer AS buffer_layer,
                    roads.id AS road_id,
                    roads.tags -> 'tags' -> 'layer' as road_layer,
                    roads.tags -> 'tags' -> 'highway' AS road_highway,
                    roads.tags -> 'tags' -> 'name' AS road_name,
                    roads.tags -> 'tags' -> 'maxspeed' as maxspeed
                FROM points LEFT OUTER JOIN {roads_table} AS roads
                ON ST_DWithin(points.geom, roads.geom, %(buffer_size)s)
                ORDER BY points.id;
            """).format(
                roads_table=roads_table,
                paths_table=paths_table
            )

            current_buffer_id = None
            current_sidepath_entry = SidepathEntry()
            with sidepath_dict_writer(stream = args.format == 'jsonl') as writer:
                for r in cur.execute(query, { 'buffer_size': 22.0, 'buffer_distance': 100.0 }):
                    row = Row(**r)
                    if current_buffer_id != row.buffer_id:
                        if current_buffer_id is not None:
                            writer.write_entry(current_buffer_id, current_sidepath_entry.result())
                        current_buffer_id = row.buffer_id
                        current_sidepath_entry = SidepathEntry()
                    current_sidepath_entry.add_row(row)
                



                


