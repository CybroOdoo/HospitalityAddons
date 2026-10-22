# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import logging
import os

from . import models
from . import wizards

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    cr = env.cr

    # ── Trigger DDL (each statement in its own savepoint) ─────────────────
    _exec(cr, """
        CREATE TABLE IF NOT EXISTS hospitality_mv_refresh_queue (
            mv_name      TEXT PRIMARY KEY,
            requested_at TIMESTAMPTZ DEFAULT now()
        )
    """, "create mv_refresh_queue table")

    _exec(cr, """
        CREATE OR REPLACE FUNCTION hospitality_reservation_availability_trigger()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO hospitality_mv_refresh_queue (mv_name, requested_at)
                VALUES ('hospitality_space_availability_mv', now())
            ON CONFLICT (mv_name) DO UPDATE
                SET requested_at = EXCLUDED.requested_at;
            RETURN NULL;
        END;
        $$
    """, "create trigger function")

    _exec(cr, """
        DROP TRIGGER IF EXISTS hospitality_reservation_availability_trg
            ON hospitality_reservation;
        CREATE TRIGGER hospitality_reservation_availability_trg
        AFTER INSERT OR DELETE OR UPDATE OF
            state, arrival, departure, space_type_id, property_id
        ON hospitality_reservation
        FOR EACH STATEMENT
        EXECUTE FUNCTION hospitality_reservation_availability_trigger()
    """, "create availability trigger")

    # ── Rebuild the availability MV to include real reserved counts ───────
    _rebuild_availability_mv(env)

    # ── RES-07 demo state advancement ─────────────────────────────────────
    _demo_advance_states(env)


def _exec(cr, sql, label="SQL"):
    """Execute a DDL statement inside a savepoint so failures are isolated."""
    cr.execute("SAVEPOINT res07_ddl")
    try:
        cr.execute(sql)
        cr.execute("RELEASE SAVEPOINT res07_ddl")
    except Exception as e:
        cr.execute("ROLLBACK TO SAVEPOINT res07_ddl")
        _logger.warning("RES-07 post_init: %s failed (non-fatal): %s", label, e)


def _rebuild_availability_mv(env):
    """Drop the PROP-05 stub MV and recreate it WITH reserved counts.

    Wrapped in a savepoint so that any failure here is fully rolled back
    and never leaves the install transaction in an aborted state.
    """
    cr = env.cr
    cr.execute("SAVEPOINT res_mv_rebuild")
    try:
        # Does the MV already exist?
        cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_matviews
                WHERE matviewname = 'hospitality_space_availability_mv'
            )
        """)
        mv_exists = cr.fetchone()[0]

        # Does it already have the reserved_count column (already rebuilt)?
        has_reserved_count = False
        if mv_exists:
            cr.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name  = 'hospitality_space_availability_mv'
                      AND column_name = 'reserved_count'
                )
            """)
            has_reserved_count = cr.fetchone()[0]

        if mv_exists and has_reserved_count:
            # Already in the desired shape — just refresh the data.
            cr.execute(
                "REFRESH MATERIALIZED VIEW hospitality_space_availability_mv"
            )
            cr.execute("RELEASE SAVEPOINT res_mv_rebuild")
            _logger.info("RES: availability MV already rebuilt; refreshed.")
            return

        # Drop the old (stub) MV, then recreate it with reservation data.
        cr.execute(
            "DROP MATERIALIZED VIEW IF EXISTS hospitality_space_availability_mv"
        )
        sql_path = os.path.join(
            os.path.dirname(__file__), 'sql', 'availability_mv_reserved.sql'
        )
        with open(sql_path, 'r') as fh:
            cr.execute(fh.read())

        cr.execute("RELEASE SAVEPOINT res_mv_rebuild")
        _logger.info("RES: rebuilt availability MV with reserved counts.")
    except Exception as e:
        # Roll back to the savepoint so the outer install transaction stays
        # healthy even if the rebuild fails for any reason.
        cr.execute("ROLLBACK TO SAVEPOINT res_mv_rebuild")
        _logger.warning("RES post_init: MV rebuild skipped: %s", e)


def _demo_advance_states(env):
    """Advance RES-07 demo reservations to their target states.

    All demo records are created as draft in the XML to avoid constraint
    errors during loading. This function advances them via the state machine.
    Silently skips if demo records are not present (non-demo install).
    """
    MODULE = 'hospitality_reservation'
    Reservation = env['hospitality.reservation']

    def _res(xmlid):
        """Return reservation record or empty recordset."""
        try:
            res_id = env['ir.model.data']._xmlid_to_res_id(
                f'{MODULE}.{xmlid}', raise_if_not_found=True
            )
            return Reservation.browse(res_id)
        except Exception:
            return Reservation

    # Check whether any demo record exists at all; skip entirely on
    # non-demo installs to avoid pointless lookups.
    probe = _res('demo_res_confirmed_vip')
    if not probe:
        return

    # Give the admin user supervisor rights so state guards pass.
    try:
        supervisor_group = env['ir.model.data']._xmlid_to_res_id(
            'hospitality_reservation.group_reservation_supervisor',
            raise_if_not_found=True,
        )
        admin = env['ir.model.data']._xmlid_to_res_id(
            'base.user_admin', raise_if_not_found=True,
        )
        admin_user = env['res.users'].browse(admin)
        group_rec  = env['res.groups'].browse(supervisor_group)
        if group_rec not in admin_user.group_ids:
            admin_user.write({'group_ids': [(4, supervisor_group)]})
        sudo_env = env(user=admin)
    except Exception as e:
        _logger.warning("RES-07 demo: could not set supervisor group: %s", e)
        sudo_env = env

    Res = sudo_env['hospitality.reservation']

    # Map xmlid → target state
    targets = [
        ('demo_res_confirmed_vip',    'confirmed'),
        ('demo_res_confirmed_acme',   'confirmed'),
        ('demo_res_confirmed_walkin', 'confirmed'),
        ('demo_res_checkedin_1',      'checked_in'),
        ('demo_res_checkedin_2',      'checked_in'),
        ('demo_res_option_expiring',  'option'),
        ('demo_res_group_a',          'confirmed'),
        ('demo_res_group_b',          'confirmed'),
        ('demo_res_sharer_primary',   'confirmed'),
        ('demo_res_sharer_secondary', 'confirmed'),
        ('demo_res_cancelled',        'cancelled'),
        ('demo_res_noshow',           'no_show'),
    ]

    for xmlid, target in targets:
        _advance(Res, env, MODULE, xmlid, target)

    # Wire sharer link after both are confirmed
    _wire_sharer(env, MODULE)


def _advance(Res, env, module, xmlid, target_state):
    """Advance one reservation to target_state using savepoint isolation."""
    cr = env.cr
    cr.execute("SAVEPOINT res07_demo")
    try:
        res_id = env['ir.model.data']._xmlid_to_res_id(
            f'{module}.{xmlid}', raise_if_not_found=True
        )
        res = Res.browse(res_id)

        if res.state == target_state:
            cr.execute("RELEASE SAVEPOINT res07_demo")
            return

        # draft → option
        if target_state == 'option' and res.state == 'draft':
            res.action_save_option()

        # draft/option → confirmed
        if target_state in ('confirmed', 'checked_in', 'checked_out',
                            'cancelled', 'no_show'):
            if res.state == 'draft':
                res.action_confirm()
            elif res.state == 'option':
                res.action_confirm()

        # confirmed → checked_in
        if target_state in ('checked_in', 'checked_out') \
                and res.state == 'confirmed':
            res.action_check_in()

        # checked_in → checked_out
        if target_state == 'checked_out' and res.state == 'checked_in':
            res.action_check_out()

        # confirmed → cancelled
        if target_state == 'cancelled' and res.state in (
                'draft', 'option', 'confirmed'):
            res.action_cancel()

        # confirmed → no_show
        if target_state == 'no_show' and res.state == 'confirmed':
            res.action_no_show()

        cr.execute("RELEASE SAVEPOINT res07_demo")
        _logger.info("RES-07 demo: %s → %s", xmlid, target_state)

    except Exception as e:
        cr.execute("ROLLBACK TO SAVEPOINT res07_demo")
        _logger.warning(
            "RES-07 demo: could not advance %s to %s: %s",
            xmlid, target_state, e,
        )


def _wire_sharer(env, module):
    """Link demo_res_sharer_secondary → demo_res_sharer_primary."""
    cr = env.cr
    cr.execute("SAVEPOINT res07_sharer")
    try:
        primary_id = env['ir.model.data']._xmlid_to_res_id(
            f'{module}.demo_res_sharer_primary', raise_if_not_found=True)
        secondary_id = env['ir.model.data']._xmlid_to_res_id(
            f'{module}.demo_res_sharer_secondary', raise_if_not_found=True)
        secondary = env['hospitality.reservation'].browse(secondary_id)
        secondary.write({'share_with_ids': [(4, primary_id)]})
        cr.execute("RELEASE SAVEPOINT res07_sharer")
        _logger.info("RES-07 demo: sharer link wired")
    except Exception as e:
        cr.execute("ROLLBACK TO SAVEPOINT res07_sharer")
        _logger.warning("RES-07 demo: sharer link failed (non-fatal): %s", e)