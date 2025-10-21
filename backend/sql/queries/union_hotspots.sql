-- TODO: This query depends on the final schemas of waf_hotspots and vpc_hotspots.
-- It needs to be adjusted to unify the columns (e.g., using NULL for missing fields).

-- Combines WAF and VPC hotspots into a single view with a common schema.
-- This allows the analytics layer to process them uniformly.

WITH waf_data AS (
    SELECT
        'WAF' AS source,
        ip,
        country,
        ua,
        uri,
        NULL AS dstport,
        NULL AS action,
        request_count AS event_count,
        NULL AS bytes
    FROM ${waf_hotspots_table}
),
vpc_data AS (
    SELECT
        'VPC' AS source,
        srcaddr AS ip,
        NULL AS country,
        NULL AS ua,
        NULL AS uri,
        dstport,
        action,
        packet_count AS event_count,
        bytes
    FROM ${vpc_hotspots_table}
)
SELECT * FROM waf_data
UNION ALL
SELECT * FROM vpc_data;
