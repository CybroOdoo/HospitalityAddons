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
from odoo.exceptions import AccessError


class HospitalityAllowance(models.Model):
    """Store approved allowance adjustments applied to folio charges."""
    _name = "hospitality.allowance"
    _description = "Folio Allowance"
    _order = "approved_at desc, id desc"
    _rec_name = "folio_line_id"

    folio_line_id = fields.Many2one(
        "hospitality.folio.line",
        string="Folio Line",
        required=True,
        ondelete="restrict",
        help="Folio line to which this allowance adjustment is applied.",
    )
    folio_id = fields.Many2one(
        "hospitality.folio",
        string="Folio",
        related="folio_line_id.folio_id",
        store=True,
        index=True,
        help="Folio containing the associated line item.",
    )
    reason = fields.Text(
        string="Reason",
        required=True,
        help="Reason for granting this allowance adjustment.",
    )
    approved_by = fields.Many2one(
        "res.users",
        string="Approved By",
        required=True,
        default=lambda self: self.env.user,
        help="User who authorized this allowance.",
    )
    approved_at = fields.Datetime(
        string="Approved At",
        default=fields.Datetime.now,
        help="Date and time when the allowance was approved.",
    )
    amount = fields.Monetary(
        string="Amount",
        required=True,
        help="Negative reduces charge.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        help="Currency of the allowance amount.",
    )
    transaction_code_id = fields.Many2one(
        "hospitality.transaction.code",
        string="Transaction Code",
        default=lambda self: self.env["hospitality.transaction.code"].search(
            [("code", "=", "ALLOWANCE_1")], limit=1
        ),
        help="Transaction code used for the allowance entry.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create allowance records after validating supervisor access."""
        if not self.env.user.has_group(
            "hospitality_folio.group_folio_supervisor"
        ):
            raise AccessError(
                "Only Folio Supervisors can create allowances."
            )
        for vals in vals_list:
            if not vals.get("transaction_code_id"):
                tc = self.env["hospitality.transaction.code"].search(
                    [("code", "=", "ALLOWANCE_1")], limit=1
                )
                if tc:
                    vals["transaction_code_id"] = tc.id
        return super().create(vals_list)