\set buffer_size 22.0
\set buffer_distance 100.0 

\set paths_table way_import_paths
\set roads_table way_import_roads


WITH points AS (
  SELECT
    id,
    nextval('buffer_nr_sequence') AS nr,
    tags -> 'tags' -> 'layer' as layer,
    (
      ST_Dump(
        ST_Union(
          CASE
            WHEN ST_Length(geom) >= :buffer_distance THEN ARRAY [
                                                ST_Startpoint(geom), 
                                                ST_Endpoint(geom), 
                                                ST_Lineinterpolatepoints(geom, :buffer_distance/st_length(geom))
                                            ]
            ELSE ARRAY [
                                                ST_Startpoint(geom), 
                                                ST_Endpoint(geom)
                                            ]
          END
        )
      )
    ).geom
  FROM
    :paths_table
  ORDER BY
    id
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
FROM
  points
  LEFT OUTER JOIN :roads_table AS roads ON ST_DWithin(points.geom, roads.geom, :buffer_size)
ORDER BY
  points.id
