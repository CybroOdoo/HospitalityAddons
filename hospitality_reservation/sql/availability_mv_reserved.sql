-- ==========================================================================
--  RES-06/07  Availability MV WITH real reservation counts
--  Rebuilds hospitality_space_availability_mv to include reserved_count
--  sourced from confirmed / checked_in reservations.
--  Drop is handled by the post_init_hook before this runs.
-- ==========================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS hospitality_space_availability_mv AS
WITH calendar AS (
    SELECT CURRENT_DATE + s.i AS the_date
    FROM generate_series(0, 729) AS s(i)
),
reservations AS (
    SELECT
        r.property_id,
        r.space_type_id,
        c.the_date,
        COUNT(*) AS reserved_count
    FROM hospitality_reservation r
    CROSS JOIN calendar c
    WHERE r.state IN ('confirmed', 'checked_in')
      AND r.arrival   <= c.the_date
      AND r.departure >  c.the_date
    GROUP BY r.property_id, r.space_type_id, c.the_date
)
SELECT
    hs.property_id,
    hs.space_type_id,
    d.the_date,
    COUNT(hs.id)                                           AS total,
    COUNT(hs.id) FILTER (
        WHERE hs.status = 'ooo'
          AND hs.ooo_from <= d.the_date
          AND hs.ooo_to   >= d.the_date
    )                                                      AS ooo,
    COUNT(hs.id) FILTER (
        WHERE hs.status = 'oos'
          AND hs.oos_from <= d.the_date
          AND hs.oos_to   >= d.the_date
    )                                                      AS oos,
    COALESCE(res.reserved_count, 0)                        AS reserved,
    COALESCE(res.reserved_count, 0)                        AS reserved_count,
    GREATEST(
        0,
        COUNT(hs.id)
        - COUNT(hs.id) FILTER (
            WHERE hs.status = 'ooo'
              AND hs.ooo_from <= d.the_date
              AND hs.ooo_to   >= d.the_date
          )
        - COUNT(hs.id) FILTER (
            WHERE hs.status = 'oos'
              AND hs.oos_from <= d.the_date
              AND hs.oos_to   >= d.the_date
          )
        - COALESCE(res.reserved_count, 0)
    )                                                      AS available
FROM
    hospitality_space hs
    CROSS JOIN calendar d
    LEFT JOIN reservations res
           ON res.property_id   = hs.property_id
          AND res.space_type_id = hs.space_type_id
          AND res.the_date      = d.the_date
WHERE
    hs.active = TRUE
GROUP BY
    hs.property_id,
    hs.space_type_id,
    d.the_date,
    res.reserved_count
WITH DATA;

-- Unique index — REQUIRED for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS ix_avail_mv_pk
    ON hospitality_space_availability_mv (property_id, space_type_id, the_date);