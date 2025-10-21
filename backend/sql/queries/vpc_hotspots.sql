-- Aggregates VPC Flow Logs to find hotspots within a given time window.
-- This identifies top talkers by source IP, destination port, and action.

SELECT
    srcaddr,
    dstport,
    action,
    COUNT(*) AS connection_count,
    SUM(packets) AS packet_count,
    SUM(bytes) AS bytes
FROM
    ${vpc_flow_logs_table}
WHERE
    -- Filter for the last 15 minutes based on log ingestion time
    from_unixtime(start) BETWEEN (NOW() - INTERVAL '15' MINUTE) AND NOW()
GROUP BY
    srcaddr,
    dstport,
    action
ORDER BY
    bytes DESC,
    packet_count DESC
LIMIT 100;
