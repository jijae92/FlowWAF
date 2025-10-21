-- VPC Flow Logs external table (JSON or Parquet format)
-- Partitioned by dt (date) and hr (hour)
-- LOCATION will be substituted by SAM parameters.

CREATE EXTERNAL TABLE IF NOT EXISTS `${database_name}`.`vpc_flow_logs` (
  version int,
  account_id string,
  interface_id string,
  srcaddr string,
  dstaddr string,
  srcport int,
  dstport int,
  protocol bigint,
  packets bigint,
  bytes bigint,
  start bigint,
  "end" bigint,
  action string,
  log_status string,
  vpc_id string,
  subnet_id string,
  instance_id string,
  tcp_flags int,
  type string,
  pkt_srcaddr string,
  pkt_dstaddr string,
  region string,
  az_id string,
  sublocation_type string,
  sublocation_id string,
  pkt_src_aws_service string,
  pkt_dst_aws_service string,
  flow_direction string,
  traffic_path array<int>
)
PARTITIONED BY (
  `dt` string,
  `hr` string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe' -- Change to ParquetSerde if using Parquet
WITH SERDEPROPERTIES (
  'ignore.malformed.json' = 'true' -- Remove if using Parquet
)
LOCATION 's3://${log_bucket_name}/vpc-flow-logs/' -- LOCATION will be substituted by SAM Parameter
TBLPROPERTIES (
  'classification'='json', -- Change to parquet if using Parquet
  'compressionType'='gzip',
  'projection.enabled'='true',
  'projection.dt.type'='date',
  'projection.dt.range'='NOW-7DAYS,NOW+1DAYS',
  'projection.dt.format'='yyyy-MM-dd',
  'projection.dt.interval'='1',
  'projection.dt.interval.unit'='DAYS',
  'projection.hr.type'='integer',
  'projection.hr.range'='0,23',
  'projection.hr.digits'='2',
  'storage.location.template'='s3://${log_bucket_name}/vpc-flow-logs/dt=${dt}/hr=${hr}/'
);