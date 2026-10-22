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


class FolioPostChargeWizard(models.TransientModel):
    """Wizard for posting charges, adjustments, or transfers to a folio."""
    _name = "hospitality.folio.post.charge.wizard"
    _description = "Post Charge Wizard"

    folio_id = fields.Many2one(
        "hospitality.folio",
        string="Folio",
        required=True,
        readonly=True,
        help="Folio to which the charge will be posted.",
    )
    transaction_code_id = fields.Many2one(
        "hospitality.transaction.code",
        string="Transaction Code",
        required=True,
        domain=[("transaction_type", "in", ("charge", "adjustment", "transfer"))],
        help="Transaction code classifying the charge or adjustment.",
    )
    qty = fields.Float(
        string="Quantity",
        required=True,
        default=1.0,
        digits=(12, 3),
        help="Quantity to post.",
    )
    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        required=True,
        help="Unit price before taxes.",
    )
    currency_id = fields.Many2one(
        related="folio_id.currency_id",
        string="Currency",
        help="Currency of the folio charge.",
    )
    reference = fields.Char(
        string="Reference",
        help="Optional description or reference text for the charge.",
    )
    window_seq = fields.Integer(
        string="Window #",
        default=1,
        help="Billing window to post this charge to (1–8).",
    )

    @api.onchange("transaction_code_id")
    def _onchange_transaction_code_id(self):
        """Validate that the selected transaction code can be used for charge posting."""
        if self.transaction_code_id and self.transaction_code_id.transaction_type \
                not in ("charge", "adjustment", "transfer"):
            raise UserError(
                "Please select a charge, adjustment, or transfer code."
            )

    def action_post(self):
        """Post the entered charge to the selected folio and close the wizard."""
        self.ensure_one()
        if not self.folio_id:
            raise UserError("No folio selected.")
        self.folio_id._post_charge(
            transaction_code_id=self.transaction_code_id,
            qty=self.qty,
            price=self.unit_price,
            ref=self.reference,
            window_seq=self.window_seq,
        )
        return {"type": "ir.actions.act_window_close"}