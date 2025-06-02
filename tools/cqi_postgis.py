import psycopg
import psycopg.rows as rows
from psycopg import Cursor
import psycopg.sql as sql
import argparse
import json
from dataclasses import dataclass
from enum import Enum
import sys
import os

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


def generate_sidepath_dict(db_url: str, roads_table: sql.Identifier, paths_table: sql.Identifier, format: str):
    with psycopg.connect(db_url) as conn:
        with conn.cursor(name = 'cqi_sidepath_dict', row_factory = rows.dict_row) as cur:
            conn.execute("CREATE TEMPORARY SEQUENCE buffer_nr_sequence;")
            query = sql.SQL("""
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
            with sidepath_dict_writer(stream = format == 'jsonl') as writer:
                for r in cur.execute(query, { 'buffer_size': 22.0, 'buffer_distance': 100.0 }):
                    row = Row(**r)
                    if current_buffer_id != row.buffer_id:
                        if current_buffer_id is not None:
                            writer.write_entry(current_buffer_id, current_sidepath_entry.result())
                        current_buffer_id = row.buffer_id
                        current_sidepath_entry = SidepathEntry()
                    current_sidepath_entry.add_row(row)


class GeomType(Enum):
    LINESTRING = 0
    POLYGON = 1
    OTHER = 3


@dataclass
class Feature:
    id: str
    properties: dict
    geometry: dict

    @staticmethod
    def from_dict(d: dict) -> "Feature":
        properties = d["properties"]
        geometry = d["geometry"]
        id = properties.get("id") or properties.get("@id")
        return Feature(id, properties, geometry)

    def geom_type(self) -> GeomType:
        match self.geometry["type"]:
            case "Polygon":
                return GeomType.POLYGON
            case "LineString":
                return GeomType.LINESTRING
            case _:
                return GeomType.OTHER

@dataclass
class Filter:
    tag: str
    op: str
    value: list[str]

    def test(self, tags: dict) -> bool: 
        match self.op:
            case 'in':
                return tags.get(self.tag) in self.value
            case 'notin':
                return tags.get(self.tag) not in self.value
            case _:
                raise ValueError(f'Operation "{self.op}" not supported')



def read_json(fname: str) -> dict:
    with open(fname) as f:
        result = json.load(f)
    return result


def get_features(d: dict) -> list[Feature]:
    return [Feature.from_dict(v) for v in d["features"]]

def create_and_clear_table(cur: Cursor, table: sql.Identifier, srid: int):
    cur.execute(sql.SQL("""
            DROP TABLE IF EXISTS {table}""").format(table=table))
    cur.execute(sql.SQL("""
            CREATE TABLE {table} (
                id text,
                tags jsonb,
                geom geometry(LINESTRING, {srid})
            )""").format(table=table, srid=sql.Literal(srid)), )
    cur.execute(sql.SQL("""
            CREATE INDEX ON {table} USING btree (id);
            CREATE INDEX ON {table} USING gist (geom);
            """).format(table=table))
 
def import_geojson(db_url: str, geojson_file: str, table_name: str, filter_file: str | None):
    linestring_features = [f for f in get_features(read_json(geojson_file)) if f.geom_type() == GeomType.LINESTRING]

    print(f"Found {len(linestring_features)} linestring features", file = sys.stderr)

    table = sql.Identifier(table_name)
    # TODO: should be a parameter
    srid = 25833

    filter = Filter(**read_json(filter_file)) if filter_file is not None else None

    # TODO: report import progress
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            create_and_clear_table(cur, table, srid)
            for f in linestring_features:
                if filter is None or filter.test(f.properties):
                    id = f.id
                    tags = { 'tags': f.properties }
                    geom = f.geometry
                    cur.execute(sql.SQL("""
                          INSERT INTO {table}
                          VALUES(
                              %(id)s,
                              %(tags)s,
                              ST_Transform(
                                  ST_GeomFromGeoJSON(%(geom)s),
                                  %(srid)s
                              )
                          )
                        """).format(table=table), { 'id': id, 'tags': json.dumps(tags), 'geom': json.dumps(geom), 'srid': srid})

def get_db_url_from_env() -> str:
    env_name = 'GEO_DATABASE_URL'
    db_url = os.getenv(env_name)
    if db_url is None:
        print('ERROR: ', f"Please specify a postgres connection url in environment variable {env_name}")
        sys.exit(-1)
    return db_url
                
def run():
    parser = argparse.ArgumentParser(description="postgis-related tools for cqi")
    # TODO: optional args for DB connection

    subparsers = parser.add_subparsers()

    def run_import(url, args):
        import_geojson(url, args.f, args.table_name, args.filter)

    parser_import = subparsers.add_parser('import', description='import geojson file into postgis')
    parser_import.add_argument("f", metavar="GEOJSON_FILE")
    parser_import.add_argument("table_name", metavar="TABLE_NAME")
    parser_import.add_argument("--filter", metavar="FILTER_JSON_FILE", required=False)
    parser_import.set_defaults(run=run_import)

    def run_generate(url, args):
        roads_table = sql.Identifier(args.roads_table)
        paths_table = sql.Identifier(args.paths_table)
        generate_sidepath_dict(url, roads_table, paths_table, args.format)

    parser_generate = subparsers.add_parser('generate-sidepath-dict', description="generate sidepath dict from roads and paths")
    parser_generate.add_argument("roads_table", metavar="ROADS_TABLE_NAME")
    parser_generate.add_argument("paths_table", metavar="PATHS_TABLE_NAME")
    parser_generate.add_argument("--format", default='jsonl', required=False, choices=['jsonl', 'json'])
    parser_generate.set_defaults(run=run_generate)

    postgis_url = get_db_url_from_env()

    args = parser.parse_args()
    args.run(postgis_url, args)

if __name__ == "__main__":
    run()



                


