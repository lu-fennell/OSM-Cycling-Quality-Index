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
\endif
\if :{?roads_table}
CREATE TEMPORARY VIEW _sidepath_estimation_roads as SELECT * FROM :roads_table;
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

-- set "jsonl"-compatible formatting
\pset format unaligned
\pset tuples_only on

-- query to generate the sidepath_dict

-- TODO:  real    29m21.904s
-- TODO: with new acc:  23m43.291s
SELECT sidepath_dict_jsonl(:buffer_distance, :buffer_size)

-- TODO real    14m29.783s
--  16m37.802s
-- SELECT * FROM sidepath_idlist_yes(:buffer_distance, :buffer_size);
--
-- 
--
-- TODO: has to run with the "not-null" acc function
-- TODO real    23m44.947s
-- TODO: check if this is correct
-- SELECT * FROM sidepath_idlist_no(:buffer_distance, :buffer_size);



\echo `date` 'Done generating sidepath dict for' :paths_table 'and' :roads_table

