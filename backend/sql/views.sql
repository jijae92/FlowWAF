-- TODO: Define views for easier querying, potentially to abstract away raw log formats.

-- Example View for WAF Logs
CREATE OR REPLACE VIEW waf_logs_view AS
SELECT
    from_unixtime(timestamp / 1000) AS event_time,
    httpRequest.clientIp AS client_ip,
    httpRequest.country AS country,
    httpRequest.uri AS uri,
    (SELECT value FROM UNNEST(httpRequest.headers) WHERE name = 'User-Agent') AS user_agent,
    terminatingRule.action AS rule_action,
    terminatingRule.ruleId AS rule_id
FROM
    ${waf_logs_table};


-- Example View for VPC Flow Logs
CREATE OR REPLACE VIEW vpc_flow_logs_view AS
SELECT
    from_unixtime(start) AS start_time,
    from_unixtime("end") AS end_time,
    srcaddr,
    dstaddr,
    srcport,
    dstport,
    protocol,
    packets,
    bytes,
    action,
    log_status
FROM
    ${vpc_flow_logs_table};
