\set QUIET on
\set ON_ERROR_STOP on


-- quietly load sidepath_lib
\o /dev/null 
\ir sidepath_lib.sql
\o

-- set parameter defaults
\if :{?buffer_size} \else  \set buffer_size 22.0 \endif
\if :{?buffer_distance} \else \set buffer_distance 100.0 \endif

-- if `paths_table` or `roads_table` parameter is set
--   setup views to override the paths and roads table we are reading from
\if :{?paths_table}
CREATE TEMPORARY VIEW _sidepath_estimation_paths as SELECT * FROM :paths_table;
\else
  \set paths_table _sidepath_estimation_paths
\endif
\if :{?roads_table}
CREATE TEMPORARY VIEW _sidepath_estimation_roads as SELECT * FROM :roads_table;
\else
  \set roads_table _sidepath_estimation_paths
\endif

-- reset checkpoint_nr_sequence
SELECT setval('checkpoint_nr_sequence', 1);
 
-- set output to outfile
\if :{?outfile}
  \o :outfile
\else
  \o
\endif

\echo `date` 'Start generating sidepath dict'

-- query to generate the sidepath_dict

-- time europe/germany:  23m43.291s
\pset format unaligned
\pset tuples_only on
SELECT sidepath_dict_jsonl(:buffer_distance, :buffer_size)

-- -- time europe/germany: 14m29.783s
-- \pset format csv
-- \pset tuples_only off
-- SELECT * FROM sidepath_idlist_yes(:buffer_distance, :buffer_size);


-- -- time europe/germany: 23m44.947s
-- -- NOTE: slower than sidepath_idlist_yes (because of left outer join), but result is much smaller
-- \pset format csv
-- \pset tuples_only off
-- SELECT * FROM sidepath_idlist_no(:buffer_distance, :buffer_size);
--


-- \pset format csv
-- \pset tuples_only off
-- SELECT * FROM sidepath_csv(:buffer_distance, :buffer_size);


\echo `date` 'Done generating sidepath dict for' :paths_table 'and' :roads_table

