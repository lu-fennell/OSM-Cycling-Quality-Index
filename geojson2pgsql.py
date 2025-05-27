import psycopg
import argparse
import json
from dataclasses import dataclass
from enum import Enum
import sys


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


def read_json(fname: str) -> dict:
    with open(fname) as f:
        result = json.load(f)
    return result


def get_features(d: dict) -> list[Feature]:
    return [Feature.from_dict(v) for v in d["features"]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="calculate cqi on postgis")
    parser.add_argument("f", metavar="GEOJSON_FILE")
    args = parser.parse_args()

    linestring_features = [f for f in get_features(read_json(args.f)) if f.geom_type() == GeomType.LINESTRING]

    print(f"Found {len(linestring_features)} linestring features", file = sys.stderr)

    with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:5432/cqi") as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM cqi_features
                        """)
            for f in linestring_features:
                id = f.id
                tags = f.properties
                geom = f.geometry
                # TODO: maybe use another query builder
                cur.execute("""
                      INSERT INTO cqi_features VALUES(%s, %s, ST_Transform(ST_GeomFromGeoJSON(%s), 25833))
                    """, (id, json.dumps(tags), json.dumps(geom)))
            r = {
                'type': 'FeatureCollection',
                'features': [],
            }

