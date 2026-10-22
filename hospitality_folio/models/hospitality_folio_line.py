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
from odoo.exceptions import UserError, AccessError


class HospitalityFolioLine(models.Model):
    """Manage individual financial transactions posted to guest folios."""
    _name = "hospitality.folio.line"
    _description = "Folio Line"
    _rec_name = "description"
    _order = "folio_id, post_date desc, id desc"

    folio_id = fields.Many2one(
        "hospitality.folio",
        string="Folio",
        required=True,
        ondelete="cascade",
        index=True,
        help="Folio to which this line belongs.",
    )
    window_id = fields.Many2one(
        "hospitality.folio.window",
        string="Window",
        ondelete="restrict",
        domain="[('folio_id', '=', folio_id)]",
        help="Billing window this line belongs to. Defaults to window 1.",
    )
    property_id = fields.Many2one(
        related="folio_id.property_id",
        store=True,
        index=True,
        help="Property associated with the folio.",
    )
    transaction_code_id = fields.Many2one(
        "hospitality.transaction.code",
        string="Transaction Code",
        required=True,
        ondelete="restrict",
        index=True,
        help="Transaction code classifying this posting.",
    )
    transaction_type = fields.Selection(
        related="transaction_code_id.transaction_type",
        store=True,
        string="Type",
        help="Transaction type derived from the transaction code.",
    )
    post_date = fields.Date(
        string="Posting Date",
        required=True,
        default=fields.Date.today,
        index=True,
        help="Date on which this transaction was posted.",
    )
    business_date = fields.Date(
        string="Business Date",
        required=True,
        help="Hotel business date assigned to this posting.",
    )
    description = fields.Char(
        string="Description",
        help="Defaults from transaction code name.",
    )
    currency_id = fields.Many2one(
        related="folio_id.currency_id",
        store=True,
        help="Currency of the transaction amount.",
    )
    qty = fields.Float(
        string="Qty",
        default=1.0,
        digits=(12, 3),
        help="Quantity of items or services charged.",
    )
    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        help="Unit price before taxes.",
    )
    tax_ids = fields.Many2many(
        "account.tax",
        "folio_line_tax_rel",
        "line_id",
        "tax_id",
        string="Taxes",
        help="Taxes applied to this transaction line.",
    )
    tax_amount = fields.Monetary(
        string="Tax Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Computed tax amount for this line.",
    )
    amount = fields.Monetary(
        string="Amount (excl. tax)",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="qty × unit_price, negative for payments/write-offs.",
    )
    amount_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="amount + tax_amount.",
    )
    reference = fields.Char(
        string="Reference",
        help="Free text note, payment reference, or POS receipt number.",
    )
    payment_reference = fields.Char(
        string="Payment Reference",
        help="Reference code or text for payment tracking.",
    )
    exchange_rate = fields.Float(
        string="Exchange Rate",
        default=1.0,
        help="Exchange rate applied if posted in a foreign currency.",
    )
    source_model = fields.Char(
        string="Source Model",
        help="Originating model name, e.g. hospitality.reservation.",
    )
    source_id = fields.Integer(
        string="Source ID",
        help="Originating record id.",
    )
    account_move_line_id = fields.Many2one(
        "account.move.line",
        string="Journal Item",
        ondelete="set null",
        copy=False,
        help="Linked accounting journal item.",
    )
    is_void = fields.Boolean(
        string="Voided",
        default=False,
        copy=False,
        help="Indicates if this transaction line has been voided.",
    )
    void_of_id = fields.Many2one(
        "hospitality.folio.line",
        string="Void Of",
        ondelete="restrict",
        index=True,
        copy=False,
        help="Original folio line that this void line cancels.",
    )
    void_date = fields.Date(
        string="Void Date",
        copy=False,
        help="Date when the line was voided.",
    )
    void_user_id = fields.Many2one(
        "res.users",
        string="Voided By",
        copy=False,
        ondelete="restrict",
        help="User who performed the void action.",
    )

    @api.depends("qty", "unit_price", "tax_ids")
    def _compute_amounts(self):
        """Compute the line subtotal, tax amount, and total amount."""
        for line in self:
            subtotal = line.qty * line.unit_price
            if line.tax_ids:
                taxes = line.tax_ids.compute_all(
                    subtotal,
                    currency=line.currency_id,
                    quantity=1.0,
                )
                line.amount = taxes["total_excluded"]
                line.tax_amount = taxes["total_included"] - taxes["total_excluded"]
                line.amount_total = taxes["total_included"]
            else:
                line.amount = subtotal
                line.tax_amount = 0.0
                line.amount_total = subtotal

    @api.onchange("transaction_code_id")
    def _onchange_transaction_code_id(self):
        """Update taxes from the selected transaction code."""
        if self.transaction_code_id:
            self.tax_ids = self.transaction_code_id.tax_ids

    @api.onchange("folio_id")
    def _onchange_folio_id(self):
        """Default window_id to window 1 of the folio."""
        if self.folio_id:
            win1 = self.folio_id.window_ids.filtered(lambda w: w.sequence == 1)
            if win1:
                self.window_id = win1[0]

    @api.constrains("void_of_id")
    def _check_void_of_id_same_folio(self):
        """Ensure a void line references a line from the same folio."""
        for line in self:
            if line.void_of_id and line.void_of_id.folio_id != line.folio_id:
                raise UserError(
                    "A void line must reference a line on the same folio."
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Create folio lines with default values and validation.

            Automatically assigns the business date, description, and default
            window, while enforcing supervisor permissions and folio state
            restrictions before creating the records.
            """
        for vals in vals_list:
            folio = None
            if vals.get("folio_id"):
                folio = self.env["hospitality.folio"].browse(vals["folio_id"])

            if not vals.get("business_date"):
                if (
                    folio
                    and folio.property_id
                    and hasattr(folio.property_id, "business_date")
                    and folio.property_id.business_date
                ):
                    vals["business_date"] = folio.property_id.business_date
                else:
                    vals["business_date"] = fields.Date.today()
            if not vals.get("description") and vals.get("transaction_code_id"):
                tc = self.env["hospitality.transaction.code"].browse(
                    vals["transaction_code_id"]
                )
                vals["description"] = tc.name
            if not vals.get("window_id") and folio:
                win1 = folio.window_ids.filtered(lambda w: w.sequence == 1)
                if win1:
                    vals["window_id"] = win1[0].id
            if vals.get("transaction_code_id"):
                tc = self.env["hospitality.transaction.code"].browse(
                    vals["transaction_code_id"]
                )
                if "tax_ids" not in vals and tc.tax_ids:
                    vals["tax_ids"] = [(6, 0, tc.tax_ids.ids)]
                if tc.requires_supervisor and not self.env.user.has_group(
                    "hospitality_folio.group_folio_supervisor"
                ):
                    raise AccessError(
                            "Transaction code '%(code)s' requires Folio Supervisor access.",
                            code=tc.code,
                    )
            if folio and folio.state not in ("open", "in_dispute"):
                raise UserError(
                    "Cannot post to folio %s — it is %s." %
                    (
                        folio.name,
                        dict(
                            self.env["hospitality.folio"]
                            ._fields["state"]
                            .selection
                        ).get(folio.state),
                    )
                )
        return super().create(vals_list)

    def write(self, vals):
        """Update folio lines while preventing changes to finalized folios.

            Only administrators can modify lines belonging to closed,
            written-off, or transferred folios.
            """
        if not self.env.is_superuser() and not self.env.is_admin():
            for line in self:
                if line.folio_id.state in ("closed", "written_off", "transferred_ar"):
                    raise UserError(
                            "Cannot modify folio line %(line)s — folio %(folio)s is %(state)s.",
                            line=line.id,
                            folio=line.folio_id.name,
                            state=line.folio_id.state,
                    )
        return super().write(vals)

    def action_void(self):
        """UI button proxy → delegates to folio._void_line."""
        for line in self:
            line.folio_id._void_line(line.id, reason="User void from UI")
