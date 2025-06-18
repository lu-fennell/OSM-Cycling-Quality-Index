-- TODO reset this sequence
CREATE SEQUENCE IF NOT EXISTS buffer_nr_sequence;

CREATE OR REPLACE FUNCTION jsonb_get_or_default(o jsonb, k text, df jsonb) RETURNS jsonb AS $$
  SELECT CASE WHEN o ? k THEN o -> k ELSE df END as result
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION text_empty_if_null(t text) RETURNS text AS $$
  SELECT CASE WHEN t IS NULL THEN '' ELSE t END as result
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION jsonb_get_set(o jsonb, t text) RETURNS jsonb AS $$
SELECT jsonb_get_or_default(o, t, '{}'::jsonb)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION jsonb_set_add(o jsonb, t text) RETURNS jsonb AS $$
  SELECT o || jsonb_build_object(t, 'true'::jsonb) 
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_add_entry(o jsonb, k text, buffer_id bigint) RETURNS jsonb AS $$
  SELECT o || jsonb_build_object(text_empty_if_null(k), jsonb_set_add(jsonb_get_set(o, k), buffer_id::text))
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION sidepath_dict_acc(acc jsonb, buffer_id bigint, road_id text, tags jsonb) RETURNS jsonb AS $$
  SELECT acc || jsonb_build_object(
    'nrs', jsonb_set_add(jsonb_get_set(acc, 'nrs'), buffer_id::text),
    'road_ids', sidepath_dict_add_entry(jsonb_get_set('road_ids'), road_id, buffer_id),
    'highways', sidepath_dict_add_entry(jsonb_get_set('highways'), tags ->> 'highway', buffer_id),
    'names', sidepath_dict_add_entry(jsonb_get_set('names'), tags ->> 'name', buffer_id)
    )
  AS result
$$ LANGUAGE SQL;

CREATE OR REPLACE AGGREGATE sidepath_dict_agg(buffer_id bigint, road_id text, tags jsonb) (
  sfunc = sidepath_dict_acc,
  stype = jsonb,
  initcond = '{}'
);