-- Views for WAF and VPC Flow Logs to simplify querying and provide a consistent time range.

-- View for WAF logs, slicing data for the last 2 hours.
CREATE OR REPLACE VIEW `${database_name}`.`slice_waf` AS
SELECT
    from_unixtime(timestamp / 1000) AS event_time,
    httpRequest.clientIp AS client_ip,
    httpRequest.country AS country,
    (SELECT value FROM UNNEST(httpRequest.headers) WHERE name = 'User-Agent') AS user_agent,
    httpRequest.uri AS uri,
    terminatingRule.action AS rule_action,
    terminatingRule.ruleId AS rule_id,
    (SELECT name FROM UNNEST(labels) LIMIT 1) AS label
FROM
    `${database_name}`.`waf_logs`
WHERE
    -- Filter for the last 2 hours based on event_time
    from_unixtime(timestamp / 1000) >= (NOW() - INTERVAL '2' HOUR);

-- View for VPC Flow logs, slicing data for the last 2 hours.
CREATE OR REPLACE VIEW `${database_name}`.`slice_vpc` AS
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
    `${database_name}`.`vpc_flow_logs`
WHERE
    -- Filter for the last 2 hours based on start_time
    from_unixtime(start) >= (NOW() - INTERVAL '2' HOUR);