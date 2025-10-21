-- AWS WAF v2 logs external table (JSON format)
-- Partitioned by dt (date) and hr (hour)
-- LOCATION will be substituted by SAM parameters.

CREATE EXTERNAL TABLE IF NOT EXISTS `${database_name}`.`waf_logs`(
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
  `dt` string,
  `hr` string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
  'ignore.malformed.json' = 'true'
)
LOCATION 's3://${log_bucket_name}/waf-logs/' -- LOCATION will be substituted by SAM Parameter
TBLPROPERTIES (
  'classification'='json',
  'compressionType'='gzip',
  'projection.enabled' = 'true',
  'projection.dt.type' = 'date',
  'projection.dt.range' = 'NOW-7DAYS,NOW+1DAYS',
  'projection.dt.format' = 'yyyy-MM-dd',
  'projection.dt.interval' = '1',
  'projection.dt.interval.unit' = 'DAYS',
  'projection.hr.type' = 'integer',
  'projection.hr.range' = '0,23',
  'projection.hr.digits' = '2',
  'storage.location.template' = 's3://${log_bucket_name}/waf-logs/dt=${dt}/hr=${hr}/'
);