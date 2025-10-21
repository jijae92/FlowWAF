-- Creates the Athena table for AWS WAF logs.
-- Assumes logs are delivered by Kinesis Firehose in a JSON format.

CREATE EXTERNAL TABLE IF NOT EXISTS `${db_name}`.`${waf_logs_table}`(
  `timestamp` bigint,
  `formatversion` int,
  `webaclid` string,
  `terminatingrule` struct<
    `ruleid`:string,
    `action`:string,
    `rulematchdetails`:array<struct<
        `conditiontype`:string,
        `location`:string,
        `matcheddata`:array<string>
    >>
  >,
  `httprequest` struct<
    `clientip`:string,
    `country`:string,
    `headers`:array<struct<`name`:string, `value`:string>>,
    `uri`:string,
    `args`:string,
    `httpversion`:string,
    `httpmethod`:string,
    `requestid`:string
  >,
  `httpresponse` struct<
    `status`:int,
    `responsecode_sent`:int
  >,
  `labels` array<struct<`name`:string>>
)
PARTITIONED BY (
  -- Partitioning by date for performance, assuming Firehose prefix `YYYY/MM/DD/HH/`
  `year` string,
  `month` string,
  `day` string,
  `hour` string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${log_bucket_name}/waf-logs/'
TBLPROPERTIES (
    'projection.enabled' = 'true',
    'projection.year.type' = 'integer',
    'projection.year.range' = '2022,2100',
    'projection.month.type' = 'integer',
    'projection.month.range' = '01,12',
    'projection.day.type' = 'integer',
    'projection.day.range' = '01,31',
    'projection.hour.type' = 'integer',
    'projection.hour.range' = '00,23',
    'storage.location.template' = 's3://${log_bucket_name}/waf-logs/${year}/${month}/${day}/${hour}/'
);
