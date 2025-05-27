WITH 
points AS (
    SELECT id, (st_dump(
                    st_union(
                        CASE WHEN st_length(geom) >= 10.0 
                        THEN ARRAY[
                                st_startpoint(geom), 
                                st_endpoint(geom), 
                                st_lineinterpolatepoints(geom, 10.0/st_length(geom))
                            ]
                        ELSE ARRAY[
                                st_startpoint(geom), 
                                st_endpoint(geom)
                            ]
                        END
                    )
                )).geom
    FROM cqi_paths
    ORDER BY id
)
SELECT 
    points.id as buffer_id, 
    roads.id as road_id,
    ST_Distance(points.geom, roads.geom) as distance,
    roads.tags -> 'highway' as road_highway,
    roads.tags -> 'name' as road_name
FROM points LEFT OUTER JOIN cqi_roads as roads ON st_dwithin(points.geom, roads.geom, 10)
ORDER BY points.id;
