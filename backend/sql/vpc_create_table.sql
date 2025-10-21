-- Creates the Athena table for VPC Flow Logs.
-- Assumes logs are stored in Parquet format in S3.
-- For text format, change SERDE and INPUTFORMAT accordingly.

CREATE EXTERNAL TABLE IF NOT EXISTS ${db_name}.${vpc_flow_logs_table} (
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
  -- Partitioning by date for performance
  year STRING,
  month STRING,
  day STRING
)
STORED AS PARQUET
LOCATION 's3://${log_bucket_name}/vpc-flow-logs/'
TBLPROPERTIES (
  -- TODO: Configure partition projection if desired, using config/partition-projection.json
  'projection.enabled'='true',
  'projection.year.type'='integer',
  'projection.year.range'='2022,2100',
  'projection.month.type'='integer',
  'projection.month.range'='01,12',
  'projection.day.type'='integer',
  'projection.day.range'='01,31',
  'storage.location.template'='s3://${log_bucket_name}/vpc-flow-logs/year=${year}/month=${month}/day=${day}'
);
