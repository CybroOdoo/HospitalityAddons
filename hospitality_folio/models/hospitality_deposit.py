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


class HospitalityDeposit(models.Model):
    """Manage guest deposits associated with hospitality folios.

        This model records deposits received from guests, tracks the
        amount applied toward folio charges, supports deposit refunds,
        and maintains the deposit lifecycle from held to applied or
        refunded.
        """
    _name = "hospitality.deposit"
    _description = "Guest Deposit"
    _order = "id desc"
    _rec_name = "folio_id"


    folio_id = fields.Many2one(
        "hospitality.folio",
        string="Folio",
        required=True,
        ondelete="restrict",
        index=True,
        help="Folio to which this deposit is allocated.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Guest",
        required=True,
        help="Guest or partner who paid the deposit.",
    )
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        required=True,
        help="Total amount of the deposit received.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        help="Currency of the deposit.",
    )
    posted_at = fields.Datetime(
        string="Posted At",
        default=fields.Datetime.now,
        help="Date and time when the deposit was posted.",
    )
    applied_amount = fields.Monetary(
        string="Applied Amount",
        currency_field="currency_id",
        compute="_compute_applied_amount",
        store=True,
        help="Amount of deposit applied against folio charges.",
    )
    refunded_amount = fields.Monetary(
        string="Refunded Amount",
        currency_field="currency_id",
        help="Amount of deposit refunded to the guest.",
    )
    state = fields.Selection(
        selection=[
            ("held", "Held"),
            ("applied", "Applied"),
            ("partially_applied", "Partially Applied"),
            ("refunded", "Refunded"),
        ],
        string="State",
        required=True,
        default="held",
        # No tracking=True: hospitality.deposit does not inherit mail.thread,
        # so it was ignored and warned about on every load. See the note on
        # hospitality.guest.id.document.verified for how to make it real.

        help="Current state of the deposit.",
    )
    refund_line_id = fields.Many2one(
        "hospitality.folio.line",
        string="Refund Line",
        copy=False,
        readonly=True,
        help="Folio line generated for deposit refund.",
    )

    @api.depends("folio_id.line_ids.amount_total", "folio_id.line_ids.source_model",
                 "folio_id.line_ids.source_id")
    def _compute_applied_amount(self):
        """Sum folio lines that were posted from this deposit."""
        for deposit in self:
            if not deposit.folio_id or deposit.state == "refunded":
                deposit.applied_amount = 0.0
                continue
            lines = deposit.folio_id.line_ids.filtered(
                lambda l: l.source_model == "hospitality.deposit"
                and l.source_id == deposit.id
                and not l.is_void
            )
            deposit.applied_amount = abs(sum(lines.mapped("amount_total")))

    def action_apply_to_folio(self, amount=None):
        """Apply held deposit to folio balance.

        :param amount: partial amount to apply; defaults to full deposit amount.
        """
        self.ensure_one()
        if self.state not in ("held", "partially_applied"):
            raise UserError("Deposit must be in 'Held' or 'Partially Applied' state to apply.")
        apply_amount = float(amount) if amount is not None else self.amount
        if apply_amount <= 0:
            raise UserError("Apply amount must be positive.")
        tc = self.env["hospitality.transaction.code"].search(
            [("code", "=", "DEPOSIT_IN")], limit=1
        )
        if not tc:
            raise UserError("DEPOSIT_IN transaction code not found.")
        new_line = self.folio_id._post_charge(
            transaction_code_id=tc,
            qty=1,
            price=-apply_amount,
            ref="Deposit #%s" % self.id,
            source_model="hospitality.deposit",
            source_id=self.id,
        )
        total_applied = self.applied_amount + apply_amount
        if total_applied >= self.amount:
            self.write({"state": "applied"})
        else:
            self.write({"state": "partially_applied"})
        return new_line

    def action_refund(self):
        """Create a refund credit line for this deposit."""
        self.ensure_one()
        if self.state == "refunded":
            raise UserError("Deposit is already refunded.")
        self._compute_applied_amount()
        if self.applied_amount > 0:
            raise UserError(
                "Cannot refund deposit: %s has already been applied. "
                "Void the application line first."
                % self.currency_id.format(self.applied_amount)
            )
        tc = self.env["hospitality.transaction.code"].search(
            [("code", "=", "DEPOSIT_REF")], limit=1
        )
        if not tc:
            raise UserError("DEPOSIT_REF transaction code not found.")
        refund_line = self.folio_id._post_charge(
            transaction_code_id=tc,
            qty=1,
            price=self.amount,
            ref="Refund #%s" % self.id,
            source_model="hospitality.deposit",
            source_id=self.id,
        )
        self.write({
            "refunded_amount": self.amount,
            "state": "refunded",
            "refund_line_id": refund_line.id,
        })
        return refund_line
