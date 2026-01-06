-- Run in Trino (DBeaver or Trino UI)
CREATE SCHEMA IF NOT EXISTS hive.iot_dw
WITH (location = 's3://iot-time-series/iot_dw/');

DROP TABLE IF EXISTS hive.iot_dw.pump;

CREATE TABLE hive.iot_dw.pump (
    event_timestamp TIMESTAMP,
    pressure DOUBLE,
    velocity DOUBLE,
    speed DOUBLE
)
WITH (
    format = 'PARQUET',
    external_location = 's3://iot-time-series/pump/'
);

-- Optional: expose CDC raw as external JSON if you later convert to Parquet/Iceberg.
