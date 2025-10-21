-- Aggregates WAF logs to find hotspots within the last ${LOOKBACK_MINUTES} minutes.
-- Detector will substitute ${LOOKBACK_MINUTES} with the actual value.

SELECT
    CAST(date_trunc('minute', from_unixtime(timestamp / 1000)) AS VARCHAR) AS minute,
    httpRequest.clientIp AS key,
    httpRequest.uri AS subkey,
    httpRequest.country AS country,
    (SELECT name FROM UNNEST(labels) LIMIT 1) AS rule_label,
    COUNT(*) AS value,
    'request_count' AS metric
FROM
    `${database_name}`.`waf_logs`
WHERE
    -- Partition pruning for efficiency
    -- Detector will substitute dt and hr with calculated values.
    dt = CAST(date_format(NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE, '%Y-%m-%d') AS VARCHAR)
    AND hr >= CAST(date_format(NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE, '%H') AS VARCHAR)
    AND from_unixtime(timestamp / 1000) >= (NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE)
GROUP BY
    1, 2, 3, 4, 5
ORDER BY
    value DESC
LIMIT ${TOP_K}; -- Detector will substitute ${TOP_K}