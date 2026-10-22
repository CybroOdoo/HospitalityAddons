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
from odoo import fields, models
from odoo.exceptions import UserError


class FolioPostPaymentWizard(models.TransientModel):
    """Wizard for posting payments or write-offs to a folio."""
    _name = "hospitality.folio.post.payment.wizard"
    _description = "Post Payment Wizard"

    folio_id = fields.Many2one(
        "hospitality.folio",
        string="Folio",
        required=True,
        readonly=True,
        help="Folio to which the payment will be posted.",
    )
    transaction_code_id = fields.Many2one(
        "hospitality.transaction.code",
        string="Payment Code",
        required=True,
        domain=[("transaction_type", "in", ("payment", "write_off"))],
        help="Transaction code used for the payment.",
    )
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        required=True,
        help="Payment amount to record.",
    )
    currency_id = fields.Many2one(
        related="folio_id.currency_id",
        string="Currency",
        help="Currency of the payment.",
    )
    payment_ref = fields.Char(
        string="Payment Reference",
        help="Card authorisation number, cheque number, etc.",
    )

    def action_post(self):
        """Post the payment to the selected folio and close the wizard."""
        self.ensure_one()
        if not self.folio_id:
            raise UserError("No folio selected.")
        if self.amount <= 0:
            raise UserError("Payment amount must be positive.")
        self.folio_id._post_payment(
            transaction_code_id=self.transaction_code_id,
            amount=self.amount,
            payment_ref=self.payment_ref,
        )
        return {"type": "ir.actions.act_window_close"}