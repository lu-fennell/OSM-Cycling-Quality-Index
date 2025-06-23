# sidepath_dict sql scripts

The psql script [generate_sidepath_dict.script.sql](./generate_sidepath_dict.script.sql) calculates a *sidepath_dict* analogously to [tools/cqi_postgis.py generate-side-path-dict](../tools/cqi_postgis.py) (and *very similar* to what [cycling_quality_index.py](../cycling_quality_index.py) generates in an intermediate step). The result is printed in `jsonl` format (lines of json-values) to stdout or a file (see below).

The script can be parameterized with the following variables:

- `outfile`: file name to print results to (default is stdout)
- `buffer_size`: a float specifying the size/radius of the checkpoints (in meters, default `22.0`)
- `buffer_distance`: a float specifying the distance between checkpoints (in meters, default `100.0`)
- `paths_table`: the name of the table (or view) containing the ways that should be considered as "paths" (i.e., potential sidepaths, default `way_import_paths`)
- `roads_table`: the name of the table (or view) containing the ways that should be considered as "roads" (i.e., the roads that could have sidepaths, default `way_import_roads`)

Example run:

```bash
psql postgresql://postgres:postgres@127.0.0.1:5432/postgres -1 -f ./generate_sidepath_dict.script.sql \
  -v outfile=sidepath_dict.jsonl \
  -v roads_table=cqi_roads \
  -v paths_table=cqi_paths
```

## Output format

Each line is a json-array with 5 elements:

1. the id of the path
2. the number of checkpoints of the path (corresponds to `checks` field in original script)
3. an object listing the number of checkpoints that are *near* to a particular way-id of a road (corresponds to `id` field in original script)
4. an object listing the checkpoint count similarly to (3), but distinguished by highway type instead of way-id (corresponds to `highway` field in original script)
5. an object listing the checkpoint count similarly to (3), but distinguished by road name instead of way-id (corresponds to `name` field in original script)
6. an object listing the maximum speed of the *nearby* roads, by highway type (corresponds to `maxspeed` field in original script)

(Here, *near* means that the checkpoint has a distance lesser than or equal to `buffer_size` of a road)

Example line:

```json
["way/1000367333", 2, {"way/37776179": 2, "way/155605290": 2, "way/374182872": 2, "way/888204998": 2, "way/1192648745": 2, "way/1192648750": 2}, {"residential": 2}, {"Lohmühlenplatz": 2, "Lohmühlenstraße": 2}, {"residential": 30}]
```

## Roadmap/TODOs

- [ ] fix remaining differences to the original *sidepath_dict* calculation
- [ ] actually perform the complete calculation for `proc_is_sidepath` and check how much slower it is
- [ ] factor out more of the query from the script (s.t. we can reasonably run it with other sql clients)
- [ ] sql functions to distinguish paths and roads and see how much slower it is separating them on-the-fly 
- [ ] check if we include output the fields (`checks` etc) in each line without blowing up the file too much
