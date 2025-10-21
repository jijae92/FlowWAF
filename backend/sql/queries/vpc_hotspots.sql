-- Aggregates VPC Flow Logs to find hotspots within the last ${LOOKBACK_MINUTES} minutes.
-- Detector will substitute ${LOOKBACK_MINUTES} with the actual value.

SELECT
    CAST(date_trunc('minute', from_unixtime(start)) AS VARCHAR) AS minute,
    srcaddr AS key,
    dstport AS subkey,
    protocol AS protocol,
    action AS action,
    COUNT(*) AS value,
    'connection_count' AS metric
FROM
    `${database_name}`.`vpc_flow_logs`
WHERE
    -- Partition pruning for efficiency
    -- Detector will substitute dt and hr with calculated values.
    dt = CAST(date_format(NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE, '%Y-%m-%d') AS VARCHAR)
    AND hr >= CAST(date_format(NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE, '%H') AS VARCHAR)
    AND from_unixtime(start) >= (NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE)
GROUP BY
    1, 2, 3, 4, 5
ORDER BY
    value DESC
LIMIT ${TOP_K}; -- Detector will substitute ${TOP_K}