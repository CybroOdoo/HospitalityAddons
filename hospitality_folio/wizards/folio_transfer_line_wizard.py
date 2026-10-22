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


class FolioTransferLineWizard(models.TransientModel):
    """Wizard for transferring folio lines between billing windows or folios."""
    _name = "hospitality.folio.transfer.line.wizard"
    _description = "Transfer Folio Line Wizard"

    folio_id = fields.Many2one(
        "hospitality.folio",
        string="Source Folio",
        required=True,
        readonly=True,
        help="Source folio from which the line will be transferred.",
    )
    line_id = fields.Many2one(
        "hospitality.folio.line",
        string="Line to Transfer",
        required=True,
        domain="[('folio_id', '=', folio_id), ('is_void', '=', False)]",
        help="Folio line selected for transfer.",
    )
    transfer_mode = fields.Selection(
        selection=[
            ("window", "Different Window (same folio)"),
            ("folio", "Different Folio"),
        ],
        string="Transfer To",
        required=True,
        default="window",
        help="Destination type for the transfer (window or another folio).",
    )
    target_window_seq = fields.Integer(
        string="Target Window #",
        default=2,
        help="Window sequence on the same folio to transfer the line to.",
    )
    target_folio_id = fields.Many2one(
        "hospitality.folio",
        string="Target Folio",
        domain="[('state', '=', 'open'), ('id', '!=', folio_id)]",
        help="Folio to receive the transferred line.",
    )
    target_folio_window_seq = fields.Integer(
        string="Window # on Target Folio",
        default=1,
        help="Window sequence on the target folio to receive the line.",
    )

    @api.onchange("transfer_mode")
    def _onchange_transfer_mode(self):
        """Reset target fields when the transfer mode changes."""
        self.target_folio_id = False
        self.target_window_seq = 2
        self.target_folio_window_seq = 1

    def action_transfer(self):
        """Transfer the selected folio line to another window or folio.

            Depending on the selected transfer mode, the wizard either moves the
            line to a different billing window within the same folio or transfers
            it to another open folio by voiding the original line and posting an
            equivalent line to the destination.
            """
        self.ensure_one()
        line = self.line_id
        if not line:
            raise UserError("Please select a line to transfer.")
        if line.is_void:
            raise UserError("Cannot transfer a voided line.")
        transfer_code = self.env["hospitality.transaction.code"].search(
            [("code", "=", "TRANSFER"), ("transaction_type", "=", "transfer")],
            limit=1,
        )
        if not transfer_code:
            raise UserError(
                "No TRANSFER transaction code found. Please create one with type 'transfer'."
            )
        if self.transfer_mode == "window":
            new_seq = self.target_window_seq
            if new_seq == (line.window_id.sequence if line.window_id else 1):
                raise UserError("Target window must be different from the source window.")
            win = self.folio_id.window_ids.filtered(lambda w: w.sequence == new_seq)
            if not win:
                raise UserError(
                    "Window %(seq)s does not exist on this folio.", seq=new_seq
                )
            self.folio_id._void_line(line.id, reason="Transferred to window %s" % new_seq)
            self.folio_id._post_charge(
                transaction_code_id=line.transaction_code_id,
                qty=line.qty,
                price=line.unit_price,
                ref=line.reference or "Transferred from window %s" % (
                    line.window_id.sequence if line.window_id else 1),
                window_seq=new_seq,
            )
        else:
            target_folio = self.target_folio_id
            if not target_folio:
                raise UserError("Please select a target folio.")
            if target_folio.state != "open":
                raise UserError("Target folio must be in Open state.")
            self.folio_id._void_line(
                line.id,
                reason=_("Transferred to folio %s") % target_folio.name,
            )
            target_folio._post_charge(
                transaction_code_id=line.transaction_code_id,
                qty=line.qty,
                price=line.unit_price,
                ref=line.reference or "Transferred from folio %s" % self.folio_id.name,
                window_seq=self.target_folio_window_seq,
            )
        return {"type": "ir.actions.act_window_close"}
