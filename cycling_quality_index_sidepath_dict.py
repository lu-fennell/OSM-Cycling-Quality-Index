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
    d.setdefault(key, 0)
    d[key] += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="calculate cqi on postgis")
    parser.add_argument("roads_table", metavar="ROADS_TABLE_NAME")
    parser.add_argument("paths_table", metavar="PATHS_TABLE_NAME")
    args = parser.parse_args()


    with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres") as conn:
        with conn.cursor(row_factory = psycopg.rows.dict_row) as cur:
            query = psycopg.sql.SQL("""
                WITH 
                points AS (
                    SELECT id, (ST_Dump(
                                    ST_Union(
                                        CASE WHEN ST_Length(geom) >= %(buffer_size)s 
                                        THEN ARRAY[
                                                ST_Startpoint(geom), 
                                                ST_Endpoint(geom), 
                                                ST_Lineinterpolatepoints(geom, %(buffer_size)s/st_length(geom))
                                            ]
                                        ELSE ARRAY[
                                                ST_Startpoint(geom), 
                                                ST_Endpoint(geom)
                                            ]
                                        END
                                    )
                                )).geom
                    FROM {paths_table}
                )
                SELECT 
                    points.id AS buffer_id, 
                    roads.id AS road_id,
                    roads.tags -> 'highway' AS road_highway,
                    roads.tags -> 'name' AS road_name
                FROM points LEFT OUTER JOIN {roads_table} AS roads ON ST_DWithin(points.geom, roads.geom, 10)
                ORDER BY points.id;
            """).format(roads_table = psycopg.sql.Identifier(args.roads_table), paths_table = psycopg.sql.Identifier(args.paths_table))

            # current_buffer_id = None
            # current_sidepath_entry = SidepathEntry(0, {}, {}, {})
            w = csv.writer(sys.stdout)
            # TODO: does it actually stream?
            for r in cur.execute(query, { 'buffer_size': 10.0 }):
                row = Row(**r)
                # if current_buffer_id != row.buffer_id:
                #     if current_buffer_id is not None:
                #         w.writerow([
                #           current_buffer_id,
                #           current_sidepath_entry.count,
                #           json.dumps(current_sidepath_entry.road_ids),
                #           json.dumps(current_sidepath_entry.highways),
                #           json.dumps(current_sidepath_entry.names)
                #         ])
                #     current_buffer_id = row.buffer_id
                #     current_sidepath_entry = SidepathEntry(0, {}, {}, {})
                # current_sidepath_entry.add_row(row)
                w.writerow([row.buffer_id, row.road_id, row.road_highway, row.road_name])
                



                


