CREATE SCHEMA IF NOT EXISTS hive.raw
WITH (location = 's3a://lake/raw/');

DROP TABLE IF EXISTS hive.raw.vision_events;

CREATE TABLE hive.raw.vision_events (
  event_id varchar,
  camera_id varchar,
  ts_start timestamp(3),
  ts_end timestamp(3),
  person_count integer,
  conf_avg double,
  conf_max double,
  frame_uri varchar
)
WITH (
  format = 'PARQUET',
  external_location = 's3a://lake/raw/vision_events/'
);