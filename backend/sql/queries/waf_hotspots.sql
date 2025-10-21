-- Aggregates WAF logs to find hotspots within a given time window.
-- This identifies top talkers by IP, country, User-Agent, and URI.

SELECT
    httpRequest.clientIp AS ip,
    httpRequest.country AS country,
    (SELECT value FROM UNNEST(httpRequest.headers) WHERE name = 'User-Agent') AS ua,
    httpRequest.uri AS uri,
    -- Extract the primary rule label if it exists
    (SELECT name FROM UNNEST(labels) LIMIT 1) AS label,
    COUNT(*) AS request_count
FROM
    ${waf_logs_table}
WHERE
    -- Partition pruning for efficiency
    -- This assumes Firehose delivers logs into a YYYY/MM/DD/HH/ structure
    year = CAST(YEAR(NOW()) AS VARCHAR)
    AND month = CAST(MONTH(NOW()) AS VARCHAR)
    AND day = CAST(DAY(NOW()) AS VARCHAR)
    AND hour = CAST(HOUR(NOW()) AS VARCHAR)
    -- Filter for the last 15 minutes
    AND from_unixtime(timestamp / 1000) BETWEEN (NOW() - INTERVAL '15' MINUTE) AND NOW()
GROUP BY
    1, 2, 3, 4, 5
ORDER BY
    request_count DESC
LIMIT 100;
