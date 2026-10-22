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

_logger = logging.getLogger(__name__)

_DEMO_PAYMENT_XMLIDS = [
    'hospitality_cashiering.demo_cash04_payment_1',
    'hospitality_cashiering.demo_cash04_payment_2',
    'hospitality_cashiering.demo_cash04_payment_3',
    'hospitality_cashiering.demo_cash04_payment_4',
    'hospitality_cashiering.demo_cash04_payment_5',
]


def _post_init_hook_cash04_demo(env):
    """CASH-04: backdate the 5 demo payment lines' create_date so they
    fall inside demo_cash04_shift's started_at/ended_at window.

    hospitality.cashier.shift._compute_expected_total() and
    _get_closeout_payment_lines() both filter hospitality.folio.line by
    create_date BETWEEN shift.started_at AND shift.ended_at. Demo data
    loads at install time ("now"), while demo_cash04_shift is
    deliberately dated "yesterday" (per the CASH-04 spec: "1 closed
    shift from yesterday"). create_date can't be set via a <field> tag
    in demo XML (it's a magic column), so without this hook the 5 demo
    payment lines would never match that window and the demo shift's
    expected_total/variance would show 0 payments instead of 5.

    Only runs if demo data is actually installed (e.g. a fresh dev
    database created with demo data enabled) — silently no-ops
    otherwise, so this is safe to leave in the manifest for production
    installs without demo data.
    """
    if not env.ref('hospitality_cashiering.demo_cash04_shift', raise_if_not_found=False):
        return

    shift = env.ref('hospitality_cashiering.demo_cash04_shift')
    lines = env['hospitality.folio.line']
    for xmlid in _DEMO_PAYMENT_XMLIDS:
        line = env.ref(xmlid, raise_if_not_found=False)
        if line:
            lines |= line

    if not lines or not shift.started_at or not shift.ended_at:
        _logger.warning(
            "CASH-04 demo: could not locate demo shift/payment lines to "
            "backdate; skipping.")
        return

    # Spread the 5 payments across the shift window (rather than
    # stacking them on one timestamp) so the closeout report shows a
    # believable sequence of postings.
    span = (shift.ended_at - shift.started_at) / (len(lines) + 1)

    # flush_model() before raw SQL, per this suite's established
    # pattern (see hospitality_reservation RES-07 demo data notes).
    lines.flush_model()
    for index, line in enumerate(lines, start=1):
        new_create_date = shift.started_at + span * index
        env.cr.execute(
            "UPDATE hospitality_folio_line SET create_date = %s WHERE id = %s",
            (new_create_date, line.id),
        )
    lines.invalidate_recordset()

    _logger.info(
        "CASH-04 demo: backdated %d payment line(s) into shift %s's window "
        "(%s -> %s).",
        len(lines), shift.name, shift.started_at, shift.ended_at)