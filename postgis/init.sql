DROP TABLE IF EXISTS cqi_features;
CREATE TABLE cqi_features (
    id text,
    tags jsonb,
    -- TODO: what to do after reproject here? new table?
    geom geometry(LINESTRING, 25833)
);
CREATE INDEX ON cqi_features USING btree (id);
CREATE INDEX ON cqi_features USING gist (geom);

