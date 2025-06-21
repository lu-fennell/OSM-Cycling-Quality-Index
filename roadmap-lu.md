# Objectives of this fork

The main objective is to implement Alex' original algorithm for CQI (cf [cycling-quality-index.py](./cycling-quality-index.py)) to an implementation that is suitable for running on the whole map of Germany in an osm2pgsql workflow.

The idea is to perform the geospatial calculations in PostGIS (instead of QGIS processing of in-memory layers). Most aspects of CQI can be calculated *locally*, i.e. by processing the tags on individual ways separately. The notable exception is the calculation of the tag `proc_sidepath` (indicating whether a path is a sidepath of a road) which requires relating a path to nearby roads. So we attempt to generate the relevant sidepath information for each path with a PostGIS-script in a first step and use it in a subsequent osm2pgsql run for the remaining local calculations. Cf also <https://wiki.openstreetmap.org/wiki/Verkehrswende-Meetup/Ideenliste-Analysen#Stra%C3%9Fenbegleitende_Wege_in_Postgis_erkennen>.

Secondary objectives of this fork are 

1. refactoring the original script for better maintainability and to allow "regression tests" with the original implementation 
2. porting the algorithm to a QGIS-Plugin to simplify further development and "interactive" adaptations of CQI in QGIS

# Repomap

- [cycling-quality-index.py](./cycling_quality_index.py): Alex' original implementation (slightly modified for exporting intermediate results)
- [cycling_quality_index_refactored](./cycling_quality_index_refactored.py) and [cqi/lib.py](./cqi/lib.py): Refactored version of the original script
- [tools/cqi_postgis.py](./tools/cqi_postgis.py): python/PostGIS script for generating sidepath information
- [sql/](./sql): pure PostGIS implementation of generating sidepath information

# Current Progress

The script `tools/cqi_postgis.py` is able to calculate sidepath information that is *very similiar* to that of the original implementation (we still need to check why they are not exactly the same). It takes about 30min for the entire German map on my laptop (AMD Ryzen 7 7840U, 32GB RAM, NVME M.2 SSD), which we consider acceptable.

A pure PostGIS implementation is in the works; it has no python dependencies is seems to be about 30% faster (i.e., 20min for the German map)
