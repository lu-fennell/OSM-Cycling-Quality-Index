CREATE SEQUENCE IF NOT EXISTS buffer_nr_sequence;
SELECT setval('buffer_nr_sequence', 1);

CREATE OR REPLACE FUNCTION text_empty_if_null(t text) RETURNS text AS $$
  SELECT CASE WHEN t IS NULL THEN '' ELSE t END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION text_both_null_or_eq(v1 text, v2 text) RETURNS boolean AS $$
  SELECT (v1 IS NULL AND v2 IS NULL) OR v1 = v2
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION bigint_osm_id_to_text(id bigint) RETURNS text AS $$
  SELECT 'way/' || id
$$ LANGUAGE SQL;


CREATE OR REPLACE FUNCTION jsonb_get_or_default(o jsonb, k text, df jsonb) RETURNS jsonb AS $$
  SELECT CASE WHEN o ? k THEN o -> k ELSE df END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION jsonb_intset_add(o jsonb, n bigint) RETURNS jsonb AS $$
  SELECT jsonb_set(o, ARRAY[n::text], 'true'::jsonb) 
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_add_entry(o jsonb, k text, buffer_id bigint) RETURNS jsonb AS $$
  SELECT CASE WHEN k is NULL
    THEN
      o
    ELSE
      jsonb_set(o, ARRAY[k], jsonb_intset_add(jsonb_get_or_default(o, k, '{}'::jsonb), buffer_id))
    END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION integer_inc_not_visited(visited jsonb, t text, n integer) RETURNS integer AS $$
  SELECT CASE WHEN visited ? t THEN n ELSE n + 1 END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_inc_field(o jsonb, visited jsonb, field text, buffer_id bigint) RETURNS jsonb AS $$
  SELECT CASE WHEN field IS NULL
    THEN
      o
    ELSE
      jsonb_set(o, ARRAY[field], to_jsonb(integer_inc_not_visited(visited -> field, buffer_id::text, jsonb_get_or_default(o, field, '0'::jsonb)::integer)))
    END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_valid_speed(v text) RETURNS boolean AS $$
  SELECT v IS NOT NULL AND v ~ '^[0-9][0-9.]*$' 
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_max_field(o jsonb, field text, value text) RETURNS jsonb AS $$
  SELECT CASE WHEN field IS NOT NULL AND sidepath_dict_valid_speed(value)
    THEN
      jsonb_set(o, ARRAY[field], to_jsonb(GREATEST(jsonb_get_or_default(o, field, to_jsonb(value::integer))::integer, value::integer)))
    ELSE
      o
    END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_add_result(result jsonb, visited jsonb, buffer_id bigint, buffer_layer text, road_id bigint, tags jsonb) RETURNS jsonb AS $$
  SELECT
    jsonb_set(
      result,
      ARRAY['checks'], to_jsonb(integer_inc_not_visited(visited -> 'nrs', buffer_id::text, (result -> 'checks')::integer))
    ) || CASE WHEN text_both_null_or_eq(buffer_layer, tags ->> 'layer')
         THEN
           jsonb_build_object(
             'id', sidepath_dict_inc_field(result -> 'id', visited -> 'road_ids', bigint_osm_id_to_text(road_id), buffer_id),
             'highway', sidepath_dict_inc_field(result -> 'highway', visited -> 'highways', tags ->> 'highway', buffer_id),
             'name', sidepath_dict_inc_field(result -> 'name', visited -> 'names', text_empty_if_null(tags ->> 'name'), buffer_id),
             'maxspeed', sidepath_dict_max_field(result -> 'maxspeed', tags ->> 'highway', (tags ->> 'maxspeed'))
           )
         ELSE
           '{}'::jsonb
         END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION  sidepath_dict_add_visited(visited jsonb, buffer_id bigint, buffer_layer text, road_id bigint, tags jsonb) RETURNS jsonb AS $$
  SELECT
    jsonb_set(
      visited,
      ARRAY['nrs'], jsonb_intset_add(visited -> 'nrs', buffer_id) 
    ) || CASE WHEN text_both_null_or_eq(buffer_layer, tags ->> 'layer')
         THEN
           jsonb_build_object(
                 'road_ids', sidepath_dict_add_entry(visited -> 'road_ids', bigint_osm_id_to_text(road_id), buffer_id),
                 'highways', sidepath_dict_add_entry(visited -> 'highways', tags ->> 'highway', buffer_id),
                 'names', sidepath_dict_add_entry(visited -> 'names', text_empty_if_null(tags ->> 'name'), buffer_id)
            )
         ELSE
           '{}'::jsonb
         END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_acc_init_if_null(acc jsonb) RETURNS jsonb AS $$
  SELECT CASE WHEN acc IS NULL
    THEN '{
      "visited": { "nrs": {}, "road_ids": {}, "highways": {}, "names": {} },
      "result": { "checks": 0, "id": {}, "highway": {}, "name": {}, "maxspeed": {} }
      }'::jsonb
    ELSE
      acc
    END
$$ LANGUAGE SQL;

-- TODO: fix this version
CREATE OR REPLACE FUNCTION sidepath_dict_acc_without_nulls(acc jsonb, buffer_id bigint, buffer_layer text, road_id bigint, tags jsonb) RETURNS jsonb AS $$
  SELECT CASE WHEN tags IS NOT NULL 
    THEN
     jsonb_build_object(
      'visited', sidepath_dict_add_visited(sidepath_dict_acc_init_if_null(acc) -> 'visited', buffer_id, buffer_layer, road_id, tags),
      'result', sidepath_dict_add_result(sidepath_dict_acc_init_if_null(acc) -> 'result', acc -> 'visited', buffer_id, buffer_layer, road_id, tags)
      )
    ELSE
      acc
    END
$$ LANGUAGE SQL;


CREATE OR REPLACE FUNCTION sidepath_dict_acc(acc jsonb, buffer_id bigint, buffer_layer text, road_id bigint, tags jsonb) RETURNS jsonb AS $$
  SELECT   jsonb_build_object(
      'visited', sidepath_dict_add_visited(acc -> 'visited', buffer_id, buffer_layer, road_id, tags),
      'result', sidepath_dict_add_result(acc -> 'result', acc -> 'visited', buffer_id, buffer_layer, road_id, tags)
      )
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_get_result(acc jsonb) RETURNS jsonb AS $$
  SELECT acc -> 'result'
$$ LANGUAGE SQL;

CREATE OR REPLACE AGGREGATE sidepath_dict_agg(buffer_id bigint, buffer_layer text, road_id bigint, tags jsonb) (
  sfunc = sidepath_dict_acc,
  stype = jsonb,
  finalfunc = sidepath_dict_get_result,
  initcond =  '{
      "visited": { "nrs": {}, "road_ids": {}, "highways": {}, "names": {} },
      "result": { "checks": 0, "id": {}, "highway": {}, "name": {}, "maxspeed": {} }
      }');

CREATE OR REPLACE FUNCTION sidepath_dict_interpolated_points(point_distance float, geom geometry) RETURNS setof geometry AS $$
  SELECT (
      ST_Dump(
        ST_Union(
          CASE
            WHEN ST_Length(geom) >= point_distance THEN ARRAY [
                                                ST_Startpoint(geom), 
                                                ST_Endpoint(geom), 
                                                ST_Lineinterpolatepoints(geom, point_distance/st_length(geom))
                                            ]
            ELSE ARRAY [
                                                ST_Startpoint(geom), 
                                                ST_Endpoint(geom)
                                            ]
          END
        )
      )
    ).geom
$$ LANGUAGE SQL;


CREATE OR REPLACE FUNCTION sidepath_dict_is_sidepath_by_checks(checks int, histogram jsonb) RETURNS boolean AS $$
  SELECT EXISTS (
    SELECT value FROM jsonb_each(histogram)
    WHERE (checks <= 2 AND value::int = checks)
    OR    checks::float * 0.66 <= value::float
  )
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_is_sidepath(entry jsonb) RETURNS boolean AS $$
  SELECT
    sidepath_dict_is_sidepath_by_checks((entry -> 'checks')::int, entry -> 'id')
    OR sidepath_dict_is_sidepath_by_checks((entry -> 'checks')::int, entry -> 'highway')
    OR sidepath_dict_is_sidepath_by_checks((entry -> 'checks')::int, entry -> 'name')
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_format_jsonl(id bigint, sidepath_dict jsonb) RETURNS jsonb as $$
  SELECT json_array('way/' || id::text, sidepath_dict -> 'checks', sidepath_dict -> 'id', sidepath_dict -> 'highway', sidepath_dict -> 'name', sidepath_dict -> 'maxspeed')
$$ LANGUAGE SQL;


CREATE OR REPLACE FUNCTION sidepath_dict_left_outer_join(buffer_distance float, buffer_size float)
  RETURNS TABLE (id bigint, nr bigint, layer text, road_id bigint, tags jsonb) AS $$
  WITH points AS (
    SELECT
      id,
      nextval('buffer_nr_sequence') AS nr,
      tags -> 'tags' ->> 'layer' as layer,
      (sidepath_dict_interpolated_points($1, geom)) AS geom
    FROM
      _sidepath_estimation_paths
    ORDER BY
      id
  )
  SELECT
    points.id, points.nr, points.layer, roads.id, roads.tags -> 'tags'
  FROM
    points
    LEFT OUTER JOIN _sidepath_estimation_roads AS roads ON ST_DWithin(points.geom, roads.geom, $2)
  ORDER BY
    points.id
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_join(buffer_distance float, buffer_size float)
  RETURNS TABLE (id bigint, nr bigint, layer text, road_id bigint, tags jsonb) AS $$
  WITH points AS (
    SELECT
      id,
      nextval('buffer_nr_sequence') AS nr,
      tags -> 'tags' ->> 'layer' as layer,
      (sidepath_dict_interpolated_points($1, geom)) AS geom
    FROM
      _sidepath_estimation_paths
    ORDER BY
      id
  )
  SELECT
    points.id, points.nr, points.layer, roads.id, roads.tags -> 'tags'
  FROM
    points
    JOIN _sidepath_estimation_roads AS roads ON ST_DWithin(points.geom, roads.geom, $2)
  ORDER BY
    points.id
$$ LANGUAGE SQL;

