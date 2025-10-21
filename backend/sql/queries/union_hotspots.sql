-- Combines WAF and VPC hotspots into a single view with a common schema.
-- This allows the analytics layer to process them uniformly.
-- Detector will substitute ${database_name}, ${LOOKBACK_MINUTES}, ${TOP_K}

WITH waf_hotspots AS (
    SELECT
        CAST(date_trunc('minute', from_unixtime(timestamp / 1000)) AS VARCHAR) AS minute,
        httpRequest.clientIp AS key,
        httpRequest.uri AS subkey,
        httpRequest.country AS country,
        (SELECT name FROM UNNEST(labels) LIMIT 1) AS rule_label,
        COUNT(*) AS value,
        'request_count' AS metric,
        'WAF' AS source_type
    FROM
        `${database_name}`.`waf_logs`
    WHERE
        dt = CAST(date_format(NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE, '%Y-%m-%d') AS VARCHAR)
        AND hr >= CAST(date_format(NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE, '%H') AS VARCHAR)
        AND from_unixtime(timestamp / 1000) >= (NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE)
    GROUP BY
        1, 2, 3, 4, 5
    LIMIT ${TOP_K}
),
vpc_hotspots AS (
    SELECT
        CAST(date_trunc('minute', from_unixtime(start)) AS VARCHAR) AS minute,
        srcaddr AS key,
        CAST(dstport AS VARCHAR) AS subkey, -- Cast to VARCHAR for union compatibility
        NULL AS country,
        NULL AS rule_label,
        COUNT(*) AS value,
        'connection_count' AS metric,
        'VPC' AS source_type
    FROM
        `${database_name}`.`vpc_flow_logs`
    WHERE
        dt = CAST(date_format(NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE, '%Y-%m-%d') AS VARCHAR)
        AND hr >= CAST(date_format(NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE, '%H') AS VARCHAR)
        AND from_unixtime(start) >= (NOW() - INTERVAL '${LOOKBACK_MINUTES}' MINUTE)
    GROUP BY
        1, 2, 3, 4, 5
    LIMIT ${TOP_K}
)
SELECT * FROM waf_hotspots
UNION ALL
SELECT * FROM vpc_hotspots
ORDER BY minute, source_type, value DESC;