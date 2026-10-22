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

class HospitalityFrontDeskCheckInWizard(models.TransientModel):
    """Wizard for checking guests into reservations."""
    _name = 'hospitality.front.desk.check.in.wizard'
    _description = 'Check-In Wizard'

    reservation_id = fields.Many2one(
        'hospitality.reservation',
        string='Reservation',
        required=True,
        help='Reservation to check in.',
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Guest',
        related='reservation_id.partner_id',
        readonly=True,
        help='Guest associated with the reservation.',
    )

    property_id = fields.Many2one(
        'hospitality.property',
        string='Property',
        compute='_compute_property_id',
        store=True,
        readonly=True,
        help='Property of the selected reservation.',
    )

    space_id = fields.Many2one(
        'hospitality.space',
        string='Room',
        required=True,
        help='Assigned room or room for the check-in.',
    )

    registration_signed = fields.Binary(
        string='Signature',
        attachment=False,
        help='Digital signature captured for guest registration.',
    )
    id_document_ids = fields.Many2many(
        'hospitality.guest.id.document',
        'fd_checkin_wiz_id_doc_rel',
        'wizard_id',
        'id_doc_id',
        string='ID Documents',
        help='ID documents verified for the primary guest.',
    )

    expected_departure = fields.Date(
        string='Expected Departure',
        help='Expected departure date.',
    )

    deposit_amount = fields.Monetary(
        string='Deposit Amount',
        currency_field='currency_id',
        help='Deposit amount collected at check-in.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help='Currency for the deposit amount.',
    )
    payment_method = fields.Selection(
        [
            ('cash', 'Cash'),
            ('card', 'Card'),
            ('ar_corp', 'AR / City Ledger'),
            ('deposit_applied', 'Apply Existing Deposit'),
            ('none', 'No Payment Now'),
        ],
        string='Payment Method',
        required=True,
        default='none',
        help='Payment method selected for check-in deposit.',
    )

    print_reg_card = fields.Boolean(
        string='Print Registration Card',
        default=True,
        help='If enabled, prints the guest registration card upon check-in.',
    )

    @api.depends('reservation_id')
    def _compute_property_id(self):
        """Compute the property and space from the selected reservation."""
        for rec in self:
            rec.property_id = rec.reservation_id.property_id if rec.reservation_id else False
            rec.space_id = rec.reservation_id.space_id if rec.reservation_id.space_id else False

    @api.onchange('reservation_id')
    def _onchange_reservation_id(self):
        """Populate check-in details from the reservation."""
        if not self.reservation_id:
            return
        res = self.reservation_id
        self.expected_departure = res.departure if hasattr(res, 'departure') else False
        self.deposit_amount = res.deposit_amount if hasattr(res, 'deposit_amount') else 0.0
        if res.partner_id:
            docs = self.env['hospitality.guest.id.document'].search(
                [('partner_id', '=', res.partner_id.id)]
            )
            self.id_document_ids = [(6, 0, docs.ids)]

    def _is_walkin_reservation(self):
        """Return whether the reservation is a walk-in."""
        res = self.reservation_id
        if not res:
            return False
        if hasattr(res, 'is_walkin') and res.is_walkin:
            return True
        if hasattr(res, 'source') and res.source == 'walk_in':
            return True
        return False

    @api.constrains('space_id')
    def _check_space_required(self):
        """Ensure a room is assigned before check-in."""
        for rec in self:
            if not rec.space_id:
                raise UserError('A room / room must be assigned before check-in.')

    @api.constrains('id_document_ids', 'reservation_id')
    def _check_id_document_required(self):
        """Require an ID document for non-walk-in guests."""
        for rec in self:
            if rec._is_walkin_reservation():
                continue
            if not rec.id_document_ids:
                raise UserError(
                    'At least one ID document is required for the primary guest '
                    'before check-in. Please capture or scan the guest\'s ID document.'
                )

    def action_check_in(self):
        """Complete the guest check-in process."""
        self.ensure_one()

        if not self.space_id:
            raise UserError('Please assign a room / room before checking in.')

        if not self._is_walkin_reservation() and not self.id_document_ids:
            raise UserError(
                'At least one ID document is required for the primary guest.'
            )

        if self.deposit_amount and self.deposit_amount > 0 \
                and self.payment_method == 'none':
            raise UserError(
                'A deposit amount is set but no payment method is selected. '
                'Please choose a payment method or set the deposit to zero.'
            )

        self.reservation_id.action_check_in()

        if self.deposit_amount and self.deposit_amount > 0 \
                and self.payment_method != 'deposit_applied':
            self._post_deposit_payment()

        action = False
        if self.print_reg_card:
            action = self._print_registration_card()

        self._issue_door_key()

        return action or {'type': 'ir.actions.act_window_close'}

    def _post_deposit_payment(self):
        """Post the guest's deposit payment."""
        pass

    def _print_registration_card(self):
        """Print the guest registration card."""
        report = self.env.ref(
            'hospitality_front_desk.action_report_registration_card',
            raise_if_not_found=False,
        )
        if report:
            return report.report_action(self.reservation_id)
        return False

    def _issue_door_key(self):
        """Issue a door key for the assigned room."""
        DoorLock = self.env.get('hospitality.door_lock')
        if DoorLock is None:
            return
        DoorLock.issue_key(self.reservation_id, self.space_id)