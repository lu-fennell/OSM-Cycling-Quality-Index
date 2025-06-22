
\set buffer_size 22.0
\set buffer_distance 100.0 

-- \set paths_table cqi_paths
-- \set roads_table cqi_roads
\set paths_table way_import_paths
\set roads_table way_import_roads

\pset format unaligned
\pset tuples_only on

\ir sidepath_lib.sql


CREATE OR REPLACE FUNCTION sidepath_dict_output_item(id text, sidepath_dict jsonb) RETURNS jsonb as $$
  SELECT json_array(id, sidepath_dict -> 'checks', sidepath_dict -> 'id', sidepath_dict -> 'highway', sidepath_dict -> 'name', sidepath_dict -> 'maxspeed')
$$ LANGUAGE SQL;

WITH points AS (
  SELECT
    id,
    nextval('buffer_nr_sequence') AS nr,
    tags -> 'tags' ->> 'layer' as layer,
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
  sidepath_dict_output_item(points.id, sidepath_dict_agg(points.nr, points.layer, roads.id, roads.tags -> 'tags'))
FROM
  points
  LEFT OUTER JOIN :roads_table AS roads ON ST_DWithin(points.geom, roads.geom, :buffer_size)
GROUP BY points.id
ORDER BY
  points.id
