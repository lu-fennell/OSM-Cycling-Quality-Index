\set QUIET on
\set ON_ERROR_STOP on

-- set parameter defaults
\if :{?buffer_size} \else  \set buffer_size 22.0 \endif
\if :{?buffer_distance} \else \set buffer_distance 100.0 \endif

\if :{?paths_table} \else \set paths_table way_import_paths \endif
\if :{?roads_table} \else \set roads_table way_import_roads \endif

-- disable output during loading of lib
\o /dev/null 

CREATE TEMPORARY VIEW _sidepath_estimation_paths as SELECT * FROM :paths_table;
CREATE TEMPORARY VIEW _sidepath_estimation_roads as SELECT * FROM :roads_table;

-- Load sidepath_lib
\ir sidepath_lib.sql
 
-- enable output again
\if :{?outfile}
  \o :outfile
\else
  \o
\endif

\echo `date` 'Start generating sidepath dict for' :paths_table 'and' :roads_table

-- set "jsonl"-compatible formatting
\pset format unaligned
\pset tuples_only on

-- query to generate the sidepath_dict

-- TODO:  real    29m21.904s
-- TODO: with new acc:  23m43.291s
SELECT sidepath_dict_format_jsonl(id, sidepath_dict_agg(nr, layer, road_id, tags)) FROM sidepath_dict_left_outer_join(:buffer_distance, :buffer_size)
GROUP BY id;

-- TODO real    14m29.783s
--  16m37.802s
-- SELECT id FROM (
--   SELECT id, sidepath_dict_agg(nr, layer, road_id, tags) AS entry FROM sidepath_dict_join(:buffer_distance, :buffer_size)
--   GROUP BY id
--   )
-- WHERE sidepath_dict_is_sidepath(entry);
-- 
--
-- TODO: has to run with the "not-null" acc function
-- TODO real    23m44.947s
-- TODO: check if this is correct
-- SELECT id FROM (
--   SELECT id, sidepath_dict_agg(nr, layer, road_id, tags) AS entry FROM sidepath_dict_left_outer_join(:buffer_distance, :buffer_size)
--   GROUP BY id
--   )
-- WHERE entry IS NULL OR NOT sidepath_dict_is_sidepath(entry);



\echo `date` 'Done generating sidepath dict for' :paths_table 'and' :roads_table

