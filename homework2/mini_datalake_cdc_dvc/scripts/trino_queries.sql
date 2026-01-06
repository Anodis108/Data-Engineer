-- Hourly aggregation
SELECT
  date_trunc('hour', event_timestamp) AS hour,
  avg(pressure) AS avg_pressure,
  avg(speed) AS avg_speed
FROM hive.iot_dw.pump
GROUP BY 1
ORDER BY 1;

-- Count alarms (>150)
SELECT count(*) AS alarm_count
FROM hive.iot_dw.pump
WHERE pressure > 150;

-- List alarm events
SELECT event_timestamp, pressure, speed
FROM hive.iot_dw.pump
WHERE pressure > 150
ORDER BY event_timestamp;
