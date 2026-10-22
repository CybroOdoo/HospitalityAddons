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
from odoo.exceptions import UserError


class HospitalityArAccount(models.Model):
    """Manage city-ledger accounts and outstanding receivable balances."""
    _name = "hospitality.ar.account"
    _description = "City-Ledger AR Account"
    _order = "partner_id, id desc"
    _rec_name = "partner_id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        index=True,
        ondelete="restrict",
        help="Partner associated with this AR account.",
    )
    property_id = fields.Many2one(
        "hospitality.property",
        string="Property",
        required=True,
        index=True,
        ondelete="restrict",
        help="Property managing this AR account.",
    )
    opened_at = fields.Datetime(
        string="Opened At",
        default=fields.Datetime.now,
        readonly=True,
        copy=False,
        help="Date and time when this AR account was created.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.company.currency_id,
        help="Currency for transactions on this account.",
    )
    balance = fields.Monetary(
        string="Balance",
        currency_field="currency_id",
        compute="_compute_balance",
        store=True,
        help="Sum of open and partially-paid AR line amounts minus payments.",
    )
    status = fields.Selection(
        selection=[
            ("open",     "Open"),
            ("on_hold",  "On Hold"),
            ("closed",   "Closed"),
        ],
        string="Status",
        required=True,
        default="open",
        help="Current status of the AR account.",
    )
    dunning_level = fields.Selection(
        selection=[
            ("none",        "None"),
            ("1st_notice",  "1st Notice"),
            ("2nd_notice",  "2nd Notice"),
            ("final",       "Final Notice"),
            ("collection",  "In Collection"),
        ],
        string="Dunning Level",
        required=True,
        default="none",
        help="Current dunning notice level for overdue balances.",
    )
    line_ids = fields.One2many(
        "hospitality.ar.line",
        "account_id",
        string="AR Lines",
        copy=False,
        help="Accounts receivable lines linked to this account.",
    )
    notes = fields.Html(
        string="Internal Notes",
        sanitize=True,
        help="Internal notes regarding this AR account.",
    )

    @api.depends(
        "line_ids.amount",
        "line_ids.paid_amount",
        "line_ids.state",
    )
    def _compute_balance(self):
        """Outstanding balance = sum of (amount − paid_amount) for non-closed lines."""
        for account in self:
            open_lines = account.line_ids.filtered(
                lambda l: l.state in ("open", "partial")
            )
            account.balance = sum(
                (l.amount - l.paid_amount) for l in open_lines
            )

    @api.model
    def _get_or_create_for_partner(self, partner_id, property_id, currency_id=None):
        """Return the open AR account for (partner, property), creating one if absent.

        :param partner_id:  res.partner record
        :param property_id: hospitality.property record
        :param currency_id: res.currency record (optional, falls back to company)
        :returns: hospitality.ar.account record
        """
        account = self.search(
            [
                ("partner_id", "=", partner_id.id),
                ("property_id", "=", property_id.id),
                ("status", "=", "open"),
            ],
            limit=1,
        )
        if not account:
            vals = {
                "partner_id": partner_id.id,
                "property_id": property_id.id,
            }
            if currency_id:
                vals["currency_id"] = currency_id.id
            account = self.create(vals)
        return account

    def action_put_on_hold(self):
        """Place the AR account on hold."""
        self.ensure_one()
        if self.status != "open":
            raise UserError(
                "Only open AR accounts can be placed on hold."
            )
        self.write({"status": "on_hold"})

    def action_reopen(self):
        """Reopen an AR account that is on hold."""
        self.ensure_one()
        if self.status != "on_hold":
            raise UserError("Only on-hold AR accounts can be re-opened.")
        self.write({"status": "open"})

    def action_close(self):
        """Close the AR account when no balance is outstanding."""
        self.ensure_one()

        if self.balance != 0.0:
            raise UserError(
                "Cannot close AR account for %(partner)s: outstanding balance is %(bal)s."
                % {
                    "partner": self.partner_id.name,
                    "bal": self.currency_id.format(self.balance),
                }
            )

        self.write({"status": "closed"})