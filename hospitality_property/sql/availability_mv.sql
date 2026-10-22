-- ==========================================================================
--  PROP-05  Availability SQL objects
--  Executed once via post_init_hook; safe to re-run (CREATE … IF NOT EXISTS /
--  OR REPLACE).
-- ==========================================================================

-- --------------------------------------------------------------------------
--  1. Materialized view
--     Keyed on (property_id, space_type_id, the_date).
--     Covers today … today + 729 (730 days inclusive).
--     available = total spaces of that type − OOO − OOS on that date.
--     reserved  = 0 stub (overridden by hospitality_reservation in Phase 1).
-- --------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS hospitality_space_availability_mv AS
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
    0::integer                                             AS reserved,
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
        -- reserved subtracted here when Phase 1 overrides
    )                                                      AS available
FROM
    hospitality_space hs
    CROSS JOIN (
        SELECT CURRENT_DATE + s.i AS the_date
        FROM generate_series(0, 729) AS s(i)
    ) d
WHERE
    hs.active = TRUE
GROUP BY
    hs.property_id,
    hs.space_type_id,
    d.the_date
WITH DATA;

-- --------------------------------------------------------------------------
--  2. Unique index (primary lookup key)
-- --------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS ix_avail_mv_pk
    ON hospitality_space_availability_mv (property_id, space_type_id, the_date);

-- --------------------------------------------------------------------------
--  3. Indexes on hospitality_space
-- --------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_space_property_type_status
    ON hospitality_space (property_id, space_type_id, status);

CREATE INDEX IF NOT EXISTS idx_space_ooo_dates
    ON hospitality_space (ooo_from, ooo_to)
    WHERE status = 'ooo';

CREATE INDEX IF NOT EXISTS idx_space_oos_dates
    ON hospitality_space (oos_from, oos_to)
    WHERE status = 'oos';

-- --------------------------------------------------------------------------
--  4. Trigger function — notifies the property on any space change
--     The Odoo cron picks up the pg_notify and refreshes the MV.
-- --------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION hospitality_space_notify_property()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify(
        'hospitality_refresh_availability',
        CAST(
            CASE TG_OP
                WHEN 'DELETE' THEN OLD.property_id
                ELSE NEW.property_id
            END
        AS text)
    );
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_space_notify_property
    ON hospitality_space;

CREATE TRIGGER trg_space_notify_property
    AFTER INSERT OR UPDATE OR DELETE
    ON hospitality_space
    FOR EACH ROW
    EXECUTE FUNCTION hospitality_space_notify_property();