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


class HospitalityArLine(models.Model):
    """Represent an individual accounts receivable entry.

        Each AR line corresponds to an outstanding amount transferred from a
        hospitality folio. It tracks payments, outstanding balance, due date,
        and the receivable's lifecycle until it is paid or written off.
        """
    _name = "hospitality.ar.line"
    _description = "City-Ledger AR Line"
    _order = "due_date, id desc"

    account_id = fields.Many2one(
        "hospitality.ar.account",
        string="AR Account",
        required=True,
        index=True,
        ondelete="cascade",
        help="AR account that owns this line item.",
    )
    folio_id = fields.Many2one(
        "hospitality.folio",
        string="Source Folio",
        index=True,
        ondelete="restrict",
        help="Folio whose balance was transferred to this AR line.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.company.currency_id,
        help="Currency of the AR line amount.",
    )
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        required=True,
        help="Original charge transferred from the folio.",
    )
    paid_amount = fields.Monetary(
        string="Paid Amount",
        currency_field="currency_id",
        default=0.0,
        help="Cumulative amount received against this AR line.",
    )
    outstanding = fields.Monetary(
        string="Outstanding",
        currency_field="currency_id",
        compute="_compute_outstanding",
        store=True,
        help="amount − paid_amount.",
    )
    due_date = fields.Date(
        string="Due Date",
        required=True,
        index=True,
        help="Date by which payment for this line is due.",
    )
    state = fields.Selection(
        selection=[
            ("open",        "Open"),
            ("partial",     "Partially Paid"),
            ("paid",        "Paid"),
            ("written_off", "Written Off"),
        ],
        string="State",
        required=True,
        default="open",
        copy=False,
        help="Current payment state of the AR line.",
    )
    description = fields.Char(
        string="Description",
        help="Auto-filled from source folio; editable.",
    )
    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        ondelete="restrict",
        copy=False,
        help="Customer invoice raised when the folio balance moved to AR.",
    )

    @api.depends("amount", "paid_amount")
    def _compute_outstanding(self):
        """Compute the remaining outstanding balance for each AR line."""
        for line in self:
            line.outstanding = line.amount - line.paid_amount

    @api.constrains("amount")
    def _check_amount_positive(self):
        """Ensure the receivable amount is greater than zero."""
        for line in self:
            if line.amount <= 0:
                raise UserError(
                    "AR line amount must be positive (got %s)." % line.amount
                )

    @api.constrains("paid_amount")
    def _check_paid_amount(self):
        """Validate that the paid amount is non-negative and does not exceed the receivable amount."""
        for line in self:
            if line.paid_amount < 0:
                raise UserError("Paid amount cannot be negative.")
            if line.paid_amount > line.amount:
                raise UserError(
                        "Paid amount (%(paid)s) cannot exceed the AR line amount (%(amt)s).",
                        paid=line.paid_amount,
                        amt=line.amount,
                )

    def write(self, vals):
        """Update AR lines and synchronize their payment state when payment information changes."""
        result = super().write(vals)
        if "paid_amount" in vals:
            for line in self:
                self._sync_state(line)
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Create AR lines and initialize their payment state."""
        records = super().create(vals_list)
        for line in records:
            self._sync_state(line)
        return records

    @staticmethod
    def _sync_state(line):
        """Derive state from paid_amount vs amount."""
        if line.state == "written_off":
            return  # never auto-revert a write-off
        if line.paid_amount <= 0:
            new_state = "open"
        elif line.paid_amount >= line.amount:
            new_state = "paid"
        else:
            new_state = "partial"
        if line.state != new_state:
            line.state = new_state

    def _payment_journal(self, journal=None):
        """Bank or cash journal to receipt an AR payment into.

        Deliberately NOT property.journal_id. That one is the sales
        journal and it raises the invoice; account.payment resolves its
        payment method lines from the journal it is posted to, and a
        sale journal has none, so posting a receipt there fails the
        "Please define a payment method line" constraint.
        """
        if journal:
            return journal
        company = (
            self.account_id.property_id.company_id or self.env.company
        )
        pay_journal = self.env["account.journal"].search(
            [("type", "in", ("bank", "cash")),
             ("company_id", "=", company.id)],
            order="sequence, id",
            limit=1,
        )
        if not pay_journal:
            raise UserError(
                "No bank or cash journal is configured for %s, so the "
                "payment cannot be receipted." % company.display_name
            )
        return pay_journal

    def action_post_payment(self, amount,journal=None):
        """Record a partial or full payment against this AR line.

        :param amount: positive float — amount being paid now.
        """
        self.ensure_one()
        if self.state in ("paid", "written_off"):
            raise UserError(
                    "AR line %(id)s is already %(state)s — no further payments accepted.",
                    id=self.id,
                    state=dict(self._fields["state"].selection).get(self.state),
            )
        if amount <= 0:
            raise UserError("Payment amount must be positive.")
        pay_journal = self._payment_journal(journal)

        payment = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.account_id.partner_id.id,
            "amount": amount,
            "currency_id": self.currency_id.id,
            "journal_id": pay_journal.id,
            # account.payment has no `ref` in Odoo 19; the field is
            # `memo`, whose inverse writes it through to move.ref.
            "memo": "AR payment - folio %s" % (self.folio_id.name or self.id),
        })
        payment.action_post()

        if self.move_id:
            (payment.move_id + self.move_id).line_ids.filtered(
                lambda l: l.account_id.account_type == "asset_receivable"
                          and not l.reconciled
            ).reconcile()

        self.write({"paid_amount": min(self.paid_amount + amount, self.amount)})
        return payment


    def action_write_off(self):
        """Write off the outstanding balance of this AR line (supervisor only)."""
        self.ensure_one()
        if not self.env.user.has_group("hospitality_folio.group_folio_supervisor"):
            from odoo.exceptions import AccessError
            raise AccessError(
                "Only a Folio Supervisor can write off AR lines."
            )
        if self.state == "written_off":
            raise UserError("AR line is already written off.")
        self.write({"state": "written_off"})
