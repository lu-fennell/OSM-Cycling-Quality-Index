import psycopg
from psycopg import Cursor
import psycopg.sql as sql
import argparse
import json
from dataclasses import dataclass
from enum import Enum
import sys
import os


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
                -- TODO: what to do after reproject here? new table?
                geom geometry(LINESTRING, {srid})
            )""").format(table=table, srid=sql.Literal(srid)), )
    cur.execute(sql.SQL("""
            CREATE INDEX ON {table} USING btree (id);
            CREATE INDEX ON {table} USING gist (geom);
            """).format(table=table))

def get_db_url_from_env() -> str:
    env_name = 'GEO_DATABASE_URL'
    db_url = os.getenv(env_name)
    if db_url is None:
        raise Exception(f"Please specify a postgres connection url in environment variable {env_name}")
    return db_url


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="import geojson files into postgis")
    parser.add_argument("f", metavar="GEOJSON_FILE")
    parser.add_argument("table_name", metavar="TABLE_NAME")
    parser.add_argument("--filter", metavar="FILTER_JSON_FILE", required=False)
    args = parser.parse_args()

    linestring_features = [f for f in get_features(read_json(args.f)) if f.geom_type() == GeomType.LINESTRING]

    print(f"Found {len(linestring_features)} linestring features", file = sys.stderr)

    table = sql.Identifier(args.table_name)
    srid = 25833

    db_url = get_db_url_from_env()
    filter = Filter(**read_json(args.filter)) if args.filter is not None else None

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

