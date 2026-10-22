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


class HospitalityRoutingInstruction(models.Model):
    """Defines routing rules for directing folio charges between billing windows or folios."""
    _name = "hospitality.routing.instruction"
    _description = "Folio Routing Instruction"
    _order = "sequence, id"

    name = fields.Char(
        string="Label",
        help="Descriptive name for this routing rule.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Evaluation order — lower numbers evaluated first.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Whether this routing rule is active.",
    )
    reservation_id = fields.Many2one(
        "hospitality.reservation",
        string="Reservation",
        ondelete="cascade",
        index=True,
        help="Leave empty for property-level rules.",
    )
    source_partner_id = fields.Many2one(
        "res.partner",
        string="Source Partner",
        ondelete="restrict",
        help="Only apply when posting partner matches. Leave empty for any.",
    )
    category_filter = fields.Selection(
        selection=[
            ("room",      "Room"),
            ("fnb",       "Food & Beverage"),
            ("telephone", "Telephone"),
            ("laundry",   "Laundry"),
            ("all",       "All Categories"),
        ],
        string="Category Filter",
        required=True,
        default="all",
        help="Only route charges that match this category.",
    )
    active_from = fields.Date(
        string="Active From",
        help="Start date from which this routing rule is active.",
    )
    active_to = fields.Date(
        string="Active To",
        help="End date until which this routing rule is active.",
    )
    target_folio_id = fields.Many2one(
        "hospitality.folio",
        string="Target Folio",
        ondelete="restrict",
        help="Leave empty to route to a different window on the same folio.",
    )
    target_window_id = fields.Many2one(
        "hospitality.folio.window",
        string="Target Window",
        ondelete="restrict",
        domain="[('folio_id','=',target_folio_id)]",
        help="Window on the target folio (or source folio) that receives the charge.",
    )
    target_window_seq = fields.Integer(
        string="Target Window #",
        related="target_window_id.sequence",
        help="Window sequence number on the target folio.",
    )
    percent = fields.Float(
        string="Percent",
        default=100.0,
        digits=(5, 2),
        help="Portion of the line amount to route (0–100). "
             "Remainder stays in the source window.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        help="Currency for the maximum amount cap.",
    )
    max_amount = fields.Monetary(
        string="Max Amount",
        currency_field="currency_id",
        default=0.0,
        help="Cap on routed amount. 0 = no cap.",
    )

    @api.constrains("percent")
    def _check_percent(self):
        """Ensure the routing percentage is within the valid range (0–100)."""
        for rec in self:
            if not (0.0 <= rec.percent <= 100.0):
                raise UserError(
                    "Routing percent must be between 0 and 100 (got %(pct)s).",
                      pct=rec.percent
                )

    @api.constrains("max_amount")
    def _check_max_amount(self):
        """Ensure the maximum routed amount is non-negative."""
        for rec in self:
            if rec.max_amount < 0:
                raise UserError(
                    "Max amount must be 0 or positive (got %(amt)s).",
                      amt=rec.max_amount
                )

    @api.model
    def _evaluate(self, folio, transaction_code_id, amount, post_date=None):
        """Return a list of routing instructions for a given posting.

        Each element is a dict::

            {
                "target_folio_id":  hospitality.folio recordset,
                "target_window_seq": int,
                "amount":           float,
            }

        If no rules match, returns a single instruction routing the full
        amount to window 1 of the source folio (i.e. default behaviour).

        :param folio:               hospitality.folio record (source)
        :param transaction_code_id: hospitality.transaction.code record
        :param amount:              float — gross charge amount
        :param post_date:           date of posting (defaults to today)
        """
        if post_date is None:
            post_date = fields.Date.today()
        tc_category = getattr(transaction_code_id, "category", "all") or "all"
        domain = [
            ("active", "=", True),
            "|",
            ("reservation_id", "=",
             folio.reservation_id.id if folio.reservation_id else False),
            ("reservation_id", "=", False),
        ]
        rules = self.search(domain, order="sequence asc, id asc")
        matched = []
        for rule in rules:
            if rule.active_from and post_date < rule.active_from:
                continue
            if rule.active_to and post_date > rule.active_to:
                continue
            if rule.category_filter != "all" and rule.category_filter != tc_category:
                continue
            if (not rule.reservation_id and rule.target_folio_id
                    and rule.target_folio_id != folio):
                continue
            matched.append(rule)
        if not matched:
            return [{
                "target_folio_id": folio,
                "target_window_seq": 1,
                "amount": amount,
            }]
        instructions = []
        remaining = amount
        for rule in matched:
            if remaining <= 0:
                break
            routed = remaining * (rule.percent / 100.0)
            if rule.max_amount > 0:
                routed = min(routed, rule.max_amount)
            routed = min(routed, remaining)
            target_folio = rule.target_folio_id or folio
            instructions.append({
                "target_folio_id": target_folio,
                "target_window_seq": rule.target_window_seq,
                "amount": routed,
            })
            remaining -= routed
        if remaining > 0.001:
            instructions.append({
                "target_folio_id": folio,
                "target_window_seq": 1,
                "amount": remaining,
            })
        return instructions
