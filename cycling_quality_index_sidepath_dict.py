import psycopg
import argparse
import json
from dataclasses import dataclass
from enum import Enum
import sys
import csv

@dataclass
class Row:
    buffer_id: str
    road_id: str
    road_highway: str
    road_name: str

@dataclass
class SidepathEntry:
    count: int
    road_ids: dict[str, int]
    highways: dict[str, int]
    names: dict[str, int]

    def add_row(self, r: Row):
        self.count += 1
        _inc_entry(self.road_ids, r.road_id)
        _inc_entry(self.highways, r.road_highway)
        _inc_entry(self.names, r.road_name)


def _inc_entry(d: dict[str, int], key: str):
    if key is not None:
        d.setdefault(key, 0)
        d[key] += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="calculate cqi on postgis")
    parser.add_argument("roads_table", metavar="ROADS_TABLE_NAME")
    parser.add_argument("paths_table", metavar="PATHS_TABLE_NAME")
    args = parser.parse_args()


    # TODO: maxspeed is missing
    with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres") as conn:
        with conn.cursor(name = 'cqi_sidepath_dict', row_factory = psycopg.rows.dict_row) as cur:
            query = psycopg.sql.SQL("""
                WITH 
                points AS (
                    SELECT id, (ST_Dump(
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
                    roads.id AS road_id,
                    roads.tags -> 'tags' -> 'highway' AS road_highway,
                    roads.tags -> 'tags' -> 'name' AS road_name
                FROM points LEFT OUTER JOIN {roads_table} AS roads ON ST_DWithin(points.geom, roads.geom, %(buffer_size)s)
                ORDER BY points.id;
            """).format(roads_table = psycopg.sql.Identifier(args.roads_table), paths_table = psycopg.sql.Identifier(args.paths_table))

            current_buffer_id = None
            current_sidepath_entry = SidepathEntry(0, {}, {}, {})
            # TODO: does it actually stream?
            for r in cur.execute(query, { 'buffer_size': 22.0, 'buffer_distance': 100.0 }):
                row = Row(**r)
                if current_buffer_id != row.buffer_id:
                    if current_buffer_id is not None:
                        print(json.dumps([
                          current_buffer_id,
                          current_sidepath_entry.count,
                          current_sidepath_entry.road_ids,
                          current_sidepath_entry.highways,
                          current_sidepath_entry.names
                        ]))
                    current_buffer_id = row.buffer_id
                    current_sidepath_entry = SidepathEntry(0, {}, {}, {})
                current_sidepath_entry.add_row(row)
                



                


