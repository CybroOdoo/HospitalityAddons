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
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HospitalityFrontDeskCheckOutWizard(models.TransientModel):
    """Wizard for checking guests out of reservations."""
    _name = 'hospitality.front.desk.check.out.wizard'
    _description = 'Check-Out Wizard'

    reservation_id = fields.Many2one(
        'hospitality.reservation',
        string='Reservation',
        required=True,
        help='Reservation to check out.',
    )

    folio_id = fields.Many2one(
        'hospitality.folio',
        string='Folio',
        compute='_compute_folio_id',
        store=False,
        help='Guest folio linked to this reservation.',
    )

    @api.depends('reservation_id')
    def _compute_folio_id(self):
        """Find the folio linked to the reservation."""
        Folio = self.env.get('hospitality.folio')
        for rec in self:
            folio = False
            if rec.reservation_id and Folio is not None \
                    and 'reservation_id' in Folio._fields:
                folio = Folio.search(
                    [('reservation_id', '=', rec.reservation_id.id)], limit=1
                )
            rec.folio_id = folio

    balance = fields.Monetary(
        string='Outstanding Balance',
        compute='_compute_balance',
        store=False,
        currency_field='currency_id',
        help='Current outstanding folio balance.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help='Currency of the folio balance.',
    )

    @api.depends('folio_id')
    def _compute_balance(self):
        """Compute the reservation's outstanding balance."""
        for rec in self:
            folio = rec.folio_id
            if folio:
                rec.balance = getattr(folio, 'balance', 0.0) or 0.0
            else:
                rec.balance = 0.0

    settle_now = fields.Boolean(
        string='Settle Balance Now',
        default=True,
        help='If checked, settle the outstanding balance immediately.',
    )
    settlement_method = fields.Selection(
        [
            ('cash', 'Cash'),
            ('card', 'Card'),
            ('ar_corp', 'AR / City Ledger'),
            ('deposit_applied', 'Apply Existing Deposit'),
            ('transfer_ar', 'Transfer to AR Account'),
        ],
        string='Settlement Method',
        help='Selected payment method for folio settlement.',
    )

    email_invoice_to = fields.Char(
        string='Email Invoice To',
        help='Email address to send the final folio invoice.',
    )

    late_checkout_fee = fields.Monetary(
        string='Late Check-Out Fee',
        currency_field='currency_id',
        default=0.0,
        help='Fee amount applied for late check-out.',
    )

    feedback_rating = fields.Selection(
        [
            ('1', '1 — Poor'),
            ('2', '2 — Fair'),
            ('3', '3 — Average'),
            ('4', '4 — Good'),
            ('5', '5 — Excellent'),
        ],
        string='Rating',
        help='Guest satisfaction rating.',
    )
    feedback_text = fields.Text(
        string='Comments',
        help='Comments or feedback provided by the guest.',
    )

    @api.onchange('reservation_id')
    def _onchange_reservation_id(self):
        """Populate the invoice email from the guest."""
        if self.reservation_id and self.reservation_id.partner_id:
            self.email_invoice_to = (
                self.reservation_id.partner_id.email or ''
            )

    def _get_balance(self):
        """Return the numeric balance; safe when folio is absent."""
        self.ensure_one()
        folio = self.folio_id
        if not folio:
            return 0.0
        return getattr(folio, 'balance', 0.0) or 0.0

    def _partner_has_open_ar(self):
        """True when the reservation partner is a corporate account."""
        partner = self.reservation_id.partner_id
        if not partner:
            return False
        return bool(getattr(partner, 'is_corporate', False))

    def _current_user_is_supervisor(self):
        """Return whether the current user is a supervisor."""
        return self.env.user.has_group(
            'hospitality_front_desk.group_front_desk_supervisor'
        )

    def action_check_out(self):
        """Complete the guest check-out process."""
        self.ensure_one()

        balance = self._get_balance()

        if self.settle_now and not self.settlement_method:
            raise UserError(
                'Please select a settlement method before checking out.'
            )

        if balance > 0:
            if self.settlement_method == 'transfer_ar':
                if not self._partner_has_open_ar():
                    raise UserError(
                        'Cannot transfer to AR: the guest partner does not '
                        'have an open corporate AR account. Please settle '
                        'the balance by another method or ask a supervisor '
                        'to override.'
                    )
            elif not self._current_user_is_supervisor():
                raise UserError(
                    'The folio still has an outstanding balance of %s. '
                    'A supervisor override is required to force check-out '
                    'without full settlement, or select "Transfer to AR".'
                    % balance
                )

        if self.late_checkout_fee and self.late_checkout_fee > 0:
            self._post_late_checkout_fee()

        if self.settle_now and self.settlement_method:
            self._settle_folio()

        self.reservation_id.action_check_out()

        if self.email_invoice_to:
            self._email_invoice()

        return {'type': 'ir.actions.act_window_close'}

    def _post_late_checkout_fee(self):
        """Post a folio line for the late check-out fee."""
        folio = self.folio_id
        if not folio:
            _logger.warning(
                'FD-03: Cannot post late check-out fee — no folio on '
                'reservation %s', self.reservation_id.name
            )
            return

        tx_code = self.env['hospitality.transaction.code'].search(
            [('code', '=', 'LATE_CO')], limit=1
        )

        line_vals = {
            'folio_id': folio.id,
            'description': 'Late Check-Out Fee',
            'qty': 1.0,
            'unit_price': self.late_checkout_fee,
        }
        if tx_code:
            line_vals['transaction_code_id'] = tx_code.id

        self.env['hospitality.folio.line'].create(line_vals)

    # def _settle_folio(self):
    #     """Mark the folio as settled or transfer to AR."""
    #     folio = self.folio_id
    #     if not folio:
    #         return
    #
    #     if self.settlement_method == 'transfer_ar':
    #         if hasattr(folio, 'action_transfer_to_ar'):
    #             folio.action_transfer_to_ar()
    #         else:
    #             folio.write({'state': 'transferred_ar'})
    #     else:
    #         if hasattr(folio, 'action_settle'):
    #             folio.action_settle(method=self.settlement_method)
    #         else:
    #             folio.write({'state': 'settled'})

    def _settle_folio(self):
        """Mark the folio as settled or transfer to AR."""
        folio = self.folio_id
        if not folio:
            return

        if self.settlement_method == 'transfer_ar':
            if hasattr(folio, 'action_transfer_to_ar'):
                folio.action_transfer_to_ar()
            else:
                folio.write({'state': 'transferred_ar'})
        else:
            if hasattr(folio, 'action_settle'):
                folio.action_settle()
            else:
                folio.write({'state': 'settled'})

    def _email_invoice(self):
        """Send the folio invoice PDF to email_invoice_to."""
        folio = self.folio_id
        if not folio:
            return

        report = self.env.ref(
            'hospitality_folio.action_report_folio_invoice',
            raise_if_not_found=False,
        )
        if not report:
            _logger.warning(
                'FD-03: Invoice report ref '
                '"hospitality_folio.action_report_folio_invoice" not found; '
                'skipping email.'
            )
            return

        template = self.env.ref(
            'hospitality_front_desk.mail_template_folio_invoice',
            raise_if_not_found=False,
        )
        if template:
            template.with_context(
                email_to=self.email_invoice_to
            ).send_mail(folio.id, force_send=True)
        else:
            try:
                pdf_content, _mime = report._render_qweb_pdf([folio.id])
                attachment = self.env['ir.attachment'].create({
                    'name': 'Invoice-%s.pdf' % (folio.name or folio.id),
                    'type': 'binary',
                    'datas': pdf_content,
                    'res_model': 'hospitality.folio',
                    'res_id': folio.id,
                })
                folio.sudo().message_post(
                    body='Please find your invoice attached.',
                    subject='Your Invoice — %s' % (folio.name or ''),
                    partner_ids=[self.reservation_id.partner_id.id],
                    attachment_ids=[attachment.id],
                    email_from=self.env.company.email or '',
                    reply_to=self.env.company.email or '',
                )
            except Exception as exc:
                _logger.warning(
                    'FD-03: Failed to email invoice for folio %s: %s',
                    folio.id, exc
                )