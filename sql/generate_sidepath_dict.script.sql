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

-- set "jsonl"-compatible formatting
\pset format unaligned
\pset tuples_only on

-- query to generate the sidepath_dict
EXECUTE sidepath_dict(:buffer_distance, :buffer_size)

