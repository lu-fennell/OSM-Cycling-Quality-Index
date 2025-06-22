-- TODO reset this sequence
CREATE SEQUENCE IF NOT EXISTS buffer_nr_sequence;

CREATE OR REPLACE FUNCTION jsonb_get_or_default(o jsonb, k text, df jsonb) RETURNS jsonb AS $$
  SELECT CASE WHEN o ? k THEN o -> k ELSE df END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION text_empty_if_null(t text) RETURNS text AS $$
  SELECT CASE WHEN t IS NULL THEN '' ELSE t END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION jsonb_get_set(o jsonb, t text) RETURNS jsonb AS $$
SELECT jsonb_get_or_default(o, t, '{}'::jsonb)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION jsonb_set_add(o jsonb, t text) RETURNS jsonb AS $$
  SELECT o || jsonb_build_object(t, 'true'::jsonb) 
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION jsonb_set_contains(o jsonb, t text) RETURNS boolean AS $$
  SELECT o ? t
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_add_entry(o jsonb, k text, buffer_id bigint) RETURNS jsonb AS $$
  SELECT o || jsonb_build_object(text_empty_if_null(k), jsonb_set_add(jsonb_get_set(o, k), buffer_id::text))
$$ LANGUAGE SQL;

-- TODO: use "intset" functions
CREATE OR REPLACE FUNCTION integer_inc_not_visited(visited jsonb, t text, n integer) RETURNS integer AS $$
  SELECT CASE WHEN jsonb_set_contains(visited, t) THEN n ELSE n + 1 END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_inc_field(o jsonb, visited jsonb, field text, buffer_id bigint) RETURNS jsonb AS $$
  SELECT o || jsonb_build_object(
    text_empty_if_null(field), integer_inc_not_visited(visited -> field, buffer_id::text, jsonb_get_or_default(o, text_empty_if_null(field), '0'::jsonb)::integer)
  )
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_valid_int(v text) RETURNS boolean AS $$
  SELECT CASE WHEN v IS NULL OR v = 'walk' THEN FALSE ELSE TRUE END
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_max_field(o jsonb, field text, value text) RETURNS jsonb AS $$
  SELECT CASE WHEN field IS NOT NULL AND sidepath_dict_valid_int(value) THEN
      o || jsonb_build_object(field, GREATEST(jsonb_get_or_default(o, field, to_jsonb(value::integer))::integer, value::integer)::integer)
    ELSE
      o
    END
$$ LANGUAGE SQL;


CREATE OR REPLACE FUNCTION sidepath_dict_add_result(result jsonb, visited jsonb, buffer_id bigint, road_id text, tags jsonb) RETURNS jsonb AS $$
  SELECT jsonb_build_object(
    'checks', integer_inc_not_visited(visited -> 'nrs', buffer_id::text, jsonb_get_or_default(result, 'checks', '0'::jsonb)::integer),
    'id', sidepath_dict_inc_field(result -> 'id', visited -> 'road_ids', road_id, buffer_id),
    'highway', sidepath_dict_inc_field(result -> 'highway', visited -> 'highways', tags ->> 'highway', buffer_id),
    'name', sidepath_dict_inc_field(result -> 'name', visited -> 'names', tags ->> 'name', buffer_id),
    'maxspeed', sidepath_dict_max_field(result -> 'maxspeed', tags ->> 'highway', (tags ->> 'maxspeed'))
  ) 
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION  sidepath_dict_add_visited(visited jsonb, buffer_id bigint, road_id text, tags jsonb) RETURNS jsonb AS $$
  SELECT jsonb_build_object(
        'nrs', jsonb_set_add(jsonb_get_set(visited, 'nrs'), buffer_id::text),
        'road_ids', sidepath_dict_add_entry(jsonb_get_set(visited, 'road_ids'), road_id, buffer_id),
        'highways', sidepath_dict_add_entry(jsonb_get_set(visited, 'highways'), tags ->> 'highway', buffer_id),
        'names', sidepath_dict_add_entry(jsonb_get_set(visited, 'names'), tags ->> 'name', buffer_id)
       )
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_acc(acc jsonb, buffer_id bigint, road_id text, tags jsonb) RETURNS jsonb AS $$
  SELECT jsonb_build_object(
      'visited', sidepath_dict_add_visited(acc -> 'visited', buffer_id, road_id, tags),
      'result', sidepath_dict_add_result(acc -> 'result', acc -> 'visited', buffer_id, road_id, tags)
      )
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_get_result(acc jsonb) RETURNS jsonb AS $$
  SELECT acc -> 'result'
$$ LANGUAGE SQL;

CREATE OR REPLACE AGGREGATE sidepath_dict_agg(buffer_id bigint, road_id text, tags jsonb) (
  sfunc = sidepath_dict_acc,
  stype = jsonb,
  finalfunc = sidepath_dict_get_result,
  -- TODO: also init visited and remove uneeded "get_or_defaults"
  initcond = '{"visited": {}, "result": {"checks": 0, "id": {}, "highway": {}, "name": {}, "maxspeed": {}}}'
);
