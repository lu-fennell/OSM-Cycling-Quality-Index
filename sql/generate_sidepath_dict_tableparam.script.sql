\set QUIET on
\set ON_ERROR_STOP on

-- set parameter defaults
\if :{?paths_table} \else \set paths_table way_import_paths \endif
\if :{?roads_table} \else \set roads_table way_import_roads \endif

-- disable output during loading of lib
\o /dev/null 

CREATE TEMPORARY VIEW _sidepath_estimation_paths as SELECT * FROM :paths_table;
CREATE TEMPORARY VIEW _sidepath_estimation_roads as SELECT * FROM :roads_table;

-- no run the original script
\ir generate_sidepath_dict.script.sql
