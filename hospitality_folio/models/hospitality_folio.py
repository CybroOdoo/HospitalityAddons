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
import logging

_logger = logging.getLogger(__name__)


class HospitalityFolio(models.Model):
    """Manage guest folios and their financial transactions."""
    _name = "hospitality.folio"
    _description = "Guest Folio"
    _inherit = ["mail.thread", "hospitality.mixin.property"]
    _order = "id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Folio Number",
        readonly=True,
        copy=False,
        default=lambda self: "New",
        help="Unique identifier for the guest folio.",
    )
    reservation_id = fields.Many2one(
        "hospitality.reservation",
        string="Reservation",
        index=True,
        ondelete="restrict",
        help="Leave empty for AR / paymaster folios.",
    )
    property_id = fields.Many2one(
        "hospitality.property",
        string="Property",
        required=True,
        index=True,
        ondelete="restrict",
        help="Property where this folio is managed.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Primary Payer",
        required=True,
        ondelete="restrict",
        tracking=True,
        help="Primary partner responsible for folio payment.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        ondelete="restrict",
        default=lambda self: self._default_currency(),
        help="Currency used for all folio entries and calculations.",
    )
    state = fields.Selection(
        selection=[
            ("open", "Open"),
            ("closed", "Closed"),
            ("in_dispute", "In Dispute"),
            ("written_off", "Written Off"),
            ("transferred_ar", "Transferred to AR"),
        ],
        string="Status",
        required=True,
        default="open",
        tracking=True,
        copy=False,
        help="Current operational status of the folio.",
    )
    opening_date = fields.Date(
        string="Opening Date",
        default=fields.Date.today,
        readonly=True,
        copy=False,
        help="Date when the folio was opened.",
    )
    closing_date = fields.Date(
        string="Closing Date",
        copy=False,
        tracking=True,
        help="Date when the folio was closed or settled.",
    )
    window_count = fields.Integer(
        string="Window Count",
        default=1,
        help="Number of active billing windows (1–8).",
    )
    window_ids = fields.One2many(
        "hospitality.folio.window",
        "folio_id",
        string="Windows",
        copy=True,
        help="Billing windows configured for split billing on this folio.",
    )
    line_ids = fields.One2many(
        "hospitality.folio.line",
        "folio_id",
        string="Folio Lines",
        copy=False,
        help="Transaction lines posted to this folio.",
    )
    deposit_ids = fields.One2many(
        "hospitality.deposit",
        "folio_id",
        string="Deposits",
        copy=False,
        help="Deposits linked to this folio.",
    )
    allowance_ids = fields.One2many(
        "hospitality.allowance",
        "folio_id",
        string="Allowances",
        copy=False,
        help="Allowance adjustments associated with this folio.",
    )
    total_charges = fields.Monetary(
        string="Total Charges",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        help="Sum of all charge and transfer lines on the folio.",
    )
    total_payments = fields.Monetary(
        string="Total Payments",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        help="Sum of all payments and write-offs posted to the folio.",
    )
    total_taxes = fields.Monetary(
        string="Total Taxes",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        help="Total tax amount computed across all folio lines.",
    )
    balance = fields.Monetary(
        string="Balance",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        help="Net balance remaining on the folio.",
    )
    invoice_ids = fields.Many2many(
        "account.move",
        "folio_invoice_rel",
        "folio_id",
        "invoice_id",
        string="Invoices / AR Moves",
        copy=False,
        groups="account.group_account_manager,account.group_account_invoice,account.group_account_readonly,base.group_portal",
        help="Invoices or accounting entries generated from this folio.",
    )
    invoice_count = fields.Integer(
        string="Invoice Count",
        compute="_compute_invoice_count",
        help="Total count of linked invoices.",
    )
    parent_folio_id = fields.Many2one(
        "hospitality.folio",
        string="Master Folio",
        ondelete="restrict",
        index=True,
        help="Shared master folio for split-billing scenarios.",
    )
    paymaster = fields.Boolean(
        string="Paymaster",
        default=False,
        help="Standalone paymaster folio — not tied to a reservation.",
    )
    notes = fields.Html(
        string="Internal Notes",
        sanitize=True,
        help="Internal remarks or comments for this folio.",
    )

    def _default_currency(self):
        """Return the property's currency, falling back to company currency."""
        property_id = (
            self.env.context.get("default_property_id")
            or self.env.context.get("property_id")
        )
        if property_id:
            prop = self.env["hospitality.property"].browse(property_id)
            if prop.exists() and prop.currency_id:
                return prop.currency_id
        return self.env.company.currency_id

    @api.model_create_multi
    def create(self, vals_list):
        """Create folios and assign the next sequence number.

            Generates a property-specific folio number when a property sequence
            is configured, otherwise falls back to the default hospitality
            folio sequence.
            """
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                property_id = vals.get("property_id")
                if property_id:
                    prop = self.env["hospitality.property"].browse(property_id)
                    seq = getattr(prop, "sequence_folio_id", None)
                    if seq:
                        vals["name"] = seq.next_by_id()
                    else:
                        vals["name"] = self.env["ir.sequence"].next_by_code(
                            "hospitality.folio"
                        ) or "New"
                else:
                    vals["name"] = self.env["ir.sequence"].next_by_code(
                        "hospitality.folio"
                    ) or "New"
        return super().create(vals_list)

    def unlink(self):
        """Delete folios that have no posted folio lines.

            Prevents deletion of folios containing posted lines to preserve
            accounting history.
            """
        for folio in self:
            line_ids = getattr(folio, "line_ids", None)
            if line_ids:
                raise UserError(
                        "Cannot delete folio %(name)s because it has posted lines. "
                        "Close or write off the folio instead.",
                        name=folio.name,
                )
        return super().unlink()

    @api.constrains("window_count")
    def _check_window_count(self):
        """Validate that the folio window count is between 1 and 8."""
        for folio in self:
            if not (1 <= folio.window_count <= 8):
                raise UserError(
                        "Window count must be between 1 and 8 (folio %(name)s).",
                        name=folio.name,
                )

    @api.depends(
        "line_ids.amount_total",
        "line_ids.tax_amount",
        "line_ids.transaction_type",
    )
    def _compute_totals(self):
        """Compute charge, payment, tax, and balance totals for the folio."""
        for folio in self:
            charges = folio.line_ids.filtered(
                lambda l: l.transaction_type in ("charge", "transfer")
            )
            payments = folio.line_ids.filtered(
                lambda l: l.transaction_type in ("payment", "write_off")
            )
            adjustments = folio.line_ids.filtered(
                lambda l: l.transaction_type == "adjustment"
            )
            folio.total_charges = sum(charges.mapped("amount_total"))
            folio.total_payments = abs(sum(payments.mapped("amount_total")))
            folio.total_taxes = sum(folio.line_ids.mapped("tax_amount"))
            folio.balance = (
                sum(charges.mapped("amount_total"))
                + sum(adjustments.mapped("amount_total"))
                + sum(payments.mapped("amount_total"))
            )

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        """Compute the number of invoices linked to the folio."""
        for folio in self:
            # Folio users may view the count via the folio workflow, but should
            # not need accounting access to account.move just to load a folio.
            folio.invoice_count = len(folio.sudo().invoice_ids)

    def action_view_reservation(self):
        """Open the reservation associated with this folio."""
        self.ensure_one()
        if not self.reservation_id:
            return {}
        return {
            "type": "ir.actions.act_window",
            "name": "Reservation",
            "res_model": "hospitality.reservation",
            "view_mode": "form",
            "res_id": self.reservation_id.id,
        }

    def action_open_invoices(self):
        """Open the invoices linked to this folio."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Invoices",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
            "context": {"default_move_type": "out_invoice" ,
                        "default_partner_id": self.partner_id.id }
        }
        if len(self.invoice_ids) == 1:
            action["view_mode"] = "form"
            action["res_id"] = self.invoice_ids[0].id
        return action

    def action_view_ar_account(self):
        """Open the Accounts Receivable account for this folio's payer."""
        self.ensure_one()
        ar_account = self.env["hospitality.ar.account"].search([
            ("partner_id", "=", self.partner_id.id),
            ("property_id", "=", self.property_id.id),
        ], limit=1)
        if not ar_account:
            return {}
        return {
            "type": "ir.actions.act_window",
            "name": "AR Account",
            "res_model": "hospitality.ar.account",
            "view_mode": "form",
            "res_id": ar_account.id,
        }

    def action_open_post_charge_wizard(self):
        """Open the wizard for posting a charge to the folio."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Post Charge",
            "res_model": "hospitality.folio.post.charge.wizard",
            "view_mode": "form",
            "target": "new",
            "domain": [],
            "context": {"default_folio_id": self.id},
        }

    def action_open_post_payment_wizard(self):
        """Open the wizard for posting a payment to the folio."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Post Payment",
            "res_model": "hospitality.folio.post.payment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_folio_id": self.id},
        }

    def action_open_transfer_line_wizard(self):
        """Open the wizard for transferring a folio line."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Transfer Line",
            "res_model": "hospitality.folio.transfer.line.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_folio_id": self.id},
        }

    def action_print_folio_tape(self):
        """Generate the folio tape report."""
        self.ensure_one()
        return self.env.ref(
            "hospitality_folio.action_report_folio_tape"
        ).report_action(self)

    def action_email_folio(self):
        """Open the email composer for sending the folio report."""
        self.ensure_one()
        report = self.env.ref("hospitality_folio.action_report_folio_tape")
        template = self.env.ref(
            "hospitality_folio.email_template_folio_tape", raise_if_not_found=False
        )
        ctx = {
            "default_model": "hospitality.folio",
            "default_res_ids": [self.id],
            "default_use_template": bool(template),
            "default_template_id": template.id if template else False,
            "default_composition_mode": "comment",
            "mark_so_as_sent": True,
        }
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(False, "form")],
            "view_id": False,
            "target": "new",
            "context": ctx,
        }

    def action_open_folio(self):
        """Entry point when a reservation checks in."""
        self.ensure_one()
        if self.state != "open":
            raise UserError(
                    "Folio %s is already %s and cannot be re-opened." %
                    (self.name,dict(self._fields["state"].selection).get(self.state)),
            )
        if not self.window_ids.filtered(lambda w: w.sequence == 1):
            self.env["hospitality.folio.window"].create(
                {
                    "folio_id": self.id,
                    "sequence": 1,
                    "label": "Room",
                    "partner_id": self.partner_id.id,
                }
            )
        return self

    # New method
    def _build_account_move(self):
        """Post the folio's operational ledger to the journal.

        Called at settle and at AR transfer. Groups non-void, non-payment
        lines by the GL account on their transaction code and writes the
        resulting journal items back onto the folio lines.
        """
        self.ensure_one()
        if self.invoice_ids:
            return self.invoice_ids  # idempotent on re-entry

        journal = self.property_id.journal_id
        if not journal:
            raise UserError(
                "Property %s has no accounting journal configured."
                % self.property_id.name
            )

        lines = self.line_ids.filtered(
            lambda l: not l.is_void and l.transaction_type != "payment"
        )
        if not lines:
            return self.env["account.move"]

        move_lines = []
        for line in lines:
            account = line.transaction_code_id.account_id
            if not account:
                raise UserError(
                    "Transaction code %s has no GL account."
                    % line.transaction_code_id.code
                )
            move_lines.append((0, 0, {
                "name": line.description or line.transaction_code_id.name,
                "account_id": account.id,
                "quantity": line.qty,
                "price_unit": line.unit_price,
                "tax_ids": [(6, 0, line.tax_ids.ids)],
            }))

        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "currency_id": self.currency_id.id,
            "journal_id": journal.id,
            # The business date, not the system date. action_settle()
            # builds the move before writing closing_date, so that field
            # is always empty here; falling through to today() would
            # date late check-outs into the next period whenever night
            # audit has not yet rolled the date forward.
            "invoice_date": (
                self.property_id.business_date
                or self.closing_date
                or fields.Date.context_today(self)
            ),
            "invoice_origin": self.name,
            "invoice_line_ids": move_lines,
        })
        move.action_post()
        self.invoice_ids = [(4, move.id)]

        # invoice_line_ids come back in creation order
        for line, move_line in zip(lines, move.invoice_line_ids):
            line.account_move_line_id = move_line.id

        return move

    def action_settle(self):
        """Close the folio."""
        self.ensure_one()
        if self.balance != 0.0:
            raise UserError(
                    "Cannot settle folio %s: outstanding balance is  %s . "
                    "Post a payment or write off the difference first." %
                    (self.name,self.currency_id.format(self.balance))
            )
        self._build_account_move()
        self.write(
            {
                "state": "closed",
                "closing_date": fields.Date.today(),
            }
        )
        self.message_post(body="Folio settled and closed.")
        return True

    def action_transfer_to_ar(self):
        """Transfer outstanding balance to Accounts Receivable."""
        self.ensure_one()
        if self.balance <= 0.0:
            raise UserError(
                    "Cannot transfer folio %s to AR: balance is %s." %
                    (self.name,self.currency_id.format(self.balance)),
            )
        move = self._build_account_move()


        ArAccount = self.env["hospitality.ar.account"]
        ar_account = ArAccount._get_or_create_for_partner(
            self.partner_id,
            self.property_id,
            self.currency_id,
        )
        self.env["hospitality.ar.line"].create({
            "account_id": ar_account.id,
            "folio_id": self.id,
            # Without the move the AR line has nothing to reconcile
            # against: action_post_payment() guards on move_id, so the
            # payment would post and the invoice would stay open,
            # counting the debtor twice in the aged balance.
            # [:1] because _build_account_move() returns the existing
            # invoice_ids when the folio was already posted, which can
            # hold more than one record.
            "move_id": move[:1].id if move else False,
            "amount": self.balance,
            "currency_id": self.currency_id.id,
            "due_date": fields.Date.context_today(self),
            "description": "Transfer from folio %s" % self.name,
        })
        self.write({"state": "transferred_ar"})
        self.message_post(body="Balance transferred to Accounts Receivable.")
        return True

    def action_dispute(self):
        """Flag the folio as in-dispute; freezes further postings."""
        self.ensure_one()
        if self.state != "open":
            raise UserError(
                    "Only open folios can be placed in dispute (folio %s is %s)." %
                    (self.name,dict(self._fields["state"].selection).get(self.state)),
            )
        self.write({"state": "in_dispute"})
        self.message_post(body="Folio placed in dispute — postings frozen.")
        return True

    def action_resolve_dispute(self):
        """Resolve a dispute and return to open state."""
        self.ensure_one()
        if self.state != "in_dispute":
            raise UserError(
                    "Folio %(name)s is not in dispute.",
                    name=self.name,
            )
        self.write({"state": "open"})
        self.message_post(body="Dispute resolved — folio re-opened.")
        return True

    def action_write_off(self):
        """Supervisor-only: zero the balance via a WRITE_OFF transaction code."""
        self.ensure_one()
        if not self.env.user.has_group("hospitality_folio.group_folio_supervisor"):
            raise AccessError("Only a Folio Supervisor can write off a folio.")
        if self.state not in ("open", "in_dispute"):
            raise UserError(
                    "Cannot write off folio %s in state %s." %
                    (self.name,dict(self._fields["state"].selection).get(self.state)),
            )

        if self.balance != 0.0:
            write_off_code = self.env["hospitality.transaction.code"].search(
                [("code", "=", "WRITE_OFF")], limit=1
            )
            if write_off_code and hasattr(self, "_post_charge"):
                self._post_charge(
                    transaction_code_id=write_off_code,
                    qty=1,
                    price=-self.balance,
                    ref="Write-off",
                )
            else:
                _logger.warning(
                    "WRITE_OFF transaction code not available for folio %s; "
                    "balance zeroed without a detail line.",
                    self.name,
                )

        self.write({"state": "written_off", "closing_date": fields.Date.today()})
        self.message_post(
            body="Folio written off by %s." % self.env.user.name
        )
        return True

    def _post_charge(
        self,
        folio_id=None,
        transaction_code_id=None,
        qty=1.0,
        price=0.0,
        ref=None,
        source_model=None,
        source_id=None,
        window_seq=None,
    ):
        """Post a charge/adjustment line to the folio."""
        self.ensure_one()
        if window_seq is None and "hospitality.routing.instruction" in self.env:
            instructions = self.env["hospitality.routing.instruction"]._evaluate(
                folio=self,
                transaction_code_id=transaction_code_id,
                amount=qty * price,
                post_date=fields.Date.today(),
            )
        else:
            target_seq = window_seq or 1
            win = self.window_ids.filtered(lambda w: w.sequence == target_seq)
            window_id = win[0].id if win else None
            if not window_id:
                win1 = self.window_ids.filtered(lambda w: w.sequence == 1)
                window_id = win1[0].id if win1 else None
            instructions = [{
                "target_folio_id": self,
                "target_window_seq": target_seq,
                "amount": qty * price,
            }]
        created_lines = self.env["hospitality.folio.line"]
        for instr in instructions:
            target_folio = instr["target_folio_id"]
            t_seq = instr["target_window_seq"]
            t_win = target_folio.window_ids.filtered(lambda w: w.sequence == t_seq)
            t_window_id = t_win[0].id if t_win else None
            if not t_window_id:
                t_win1 = target_folio.window_ids.filtered(lambda w: w.sequence == 1)
                t_window_id = t_win1[0].id if t_win1 else None
            split_price = instr["amount"] / qty if qty else instr["amount"]
            vals = {
                "folio_id": target_folio.id,
                "transaction_code_id": transaction_code_id.id,
                "qty": qty,
                "unit_price": split_price,
                "reference": ref,
                "is_void": False,
            }
            if t_window_id:
                vals["window_id"] = t_window_id
            if source_model:
                vals["source_model"] = source_model
            if source_id:
                vals["source_id"] = source_id
            created_lines |= self.env["hospitality.folio.line"].create(vals)
        return created_lines[0] if len(created_lines) == 1 else created_lines

    def _post_payment(
        self,
        folio_id=None,
        transaction_code_id=None,
        amount=0.0,
        payment_ref=None,
    ):
        """Post a payment line to the folio (credit-signed)."""
        self.ensure_one()
        if transaction_code_id.transaction_type not in ("payment", "write_off"):
            raise UserError(
                    "Transaction code '%(code)s' is not a payment or write-off code.",
                    code=transaction_code_id.code,
            )
        line = self.env["hospitality.folio.line"].create(
            {
                "folio_id": self.id,
                "transaction_code_id": transaction_code_id.id,
                "qty": 1.0,
                "unit_price": -abs(amount),
                "reference": payment_ref,
            }
        )
        if self.reservation_id and hasattr(self.reservation_id, "deposit_paid"):
            self.reservation_id.deposit_paid += amount
        return line

    def _void_line(self, line_id, reason=None):
        """Supervisor only: create a negative mirror line.

        Returns the newly created void line.
        """
        self.ensure_one()
        line = self.env["hospitality.folio.line"].browse(line_id)
        if line.folio_id != self:
            raise UserError("The line does not belong to this folio.")
        if not self.env.user.has_group(
            "hospitality_folio.group_folio_supervisor"
        ):
            raise AccessError("Only a Folio Supervisor can void lines.")
        if line.is_void:
            raise UserError("This line is already voided.")
        mirror_vals = {
            "folio_id": self.id,
            "window_id": line.window_id.id,
            "transaction_code_id": line.transaction_code_id.id,
            "description": reason or "Void: %s" % (line.description or line.reference or line.id),
            "qty": -line.qty,
            "unit_price": line.unit_price,
            "reference": reason or "Void of line %s" % line.id,
            "is_void": True,
            "void_of_id": line.id,
            "post_date": fields.Date.today(),
            "business_date": line.business_date,
            "source_model": line.source_model,
            "source_id": line.source_id,
        }
        if line.tax_ids:
            mirror_vals["tax_ids"] = [(6, 0, line.tax_ids.ids)]
        void_line = self.env["hospitality.folio.line"].create(mirror_vals)
        self.message_post(
            body=(
                    "Line voided: %(code)s %(ref)s by %(user)s."
                    % {
                        "code": line.transaction_code_id.code,
                        "ref": line.reference or "",
                        "user": self.env.user.name,
                    }
            )
        )
        return void_line
