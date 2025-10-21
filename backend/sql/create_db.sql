-- Creates the database for logs and analytics if it doesn't already exist.
CREATE DATABASE IF NOT EXISTS ${db_name}
COMMENT 'Database for WAF and VPC Flow Log analysis';
