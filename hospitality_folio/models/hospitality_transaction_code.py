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
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HospitalityTransactionCode(models.Model):
    """Extend hospitality.transaction.code with transaction type and category filter """
    _inherit = "hospitality.transaction.code"

    transaction_type = fields.Selection(
        selection=[
            ("charge", "Charge"),
            ("payment", "Payment"),
            ("adjustment", "Adjustment"),
            ("write_off", "Write Off"),
            ("transfer", "Transfer"),
        ],
        string="Type",
        required=True,
        default="charge",
        help=(
            "charge     — increases balance (room, F&B, incidentals).\n"
            "payment    — decreases balance (cash, credit card).\n"
            "adjustment — positive or negative correction.\n"
            "write_off  — supervisor-only balance zeroing.\n"
            "transfer   — moves a charge to another folio/window."
        ),
    )
    requires_supervisor = fields.Boolean(
        string="Supervisor Required",
        default=False,
        help="If checked, only Folio Supervisors may post lines with this code.",
    )
    # Replaced name_get function

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}"

    @api.constrains('account_id', 'transaction_type')
    def _check_postable_has_account(self):
        """A postable code without a GL account fails at configuration
        time rather than at folio close.

        Skipped while data files are loading. The codes ship before any
        admin has mapped them onto a chart of accounts - and the chart
        differs per company - so enforcing this during install would
        abort the module's own data load on the first record. Odoo
        guards the same way in auth_signup and hr_holidays.

        The hard stop still exists at the point of use:
        hospitality.folio._build_account_move() refuses to post a line
        whose code has no account, naming the code.
        """
        if self.env.context.get('install_mode'):
            return
        postable = ('charge', 'payment', 'adjustment', 'write_off')
        for rec in self:
            if rec.transaction_type in postable and not rec.account_id:
                raise ValidationError(
                    "Transaction code '%s' is postable and must have a "
                    "GL account." % rec.code
                )