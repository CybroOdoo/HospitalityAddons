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


class HospitalityWalkInWizard(models.TransientModel):
    """Front desk wizard for registering walk-in guests.

       Creates or selects a guest profile, creates a reservation,
       performs check-in, and ensures an open folio exists.
       """
    _name = 'hospitality.walk.in.wizard'
    _description = 'Walk-In Wizard'

    mode = fields.Selection(
        [
            ('existing_partner', 'Existing Guest'),
            ('new_partner', 'New Guest'),
        ],
        string='Guest Source',
        required=True,
        default='new_partner',
        help='Choose whether to select an existing guest or create a new guest profile.',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Existing Guest',
        help='Select an existing guest record.',
    )
    new_partner_name = fields.Char(
        string='Guest Name',
        help='Full name of the new guest.',
    )
    new_partner_email = fields.Char(
        string='Email',
        help='Email address of the new guest.',
    )
    new_partner_phone = fields.Char(
        string='Phone',
        help='Phone number of the new guest.',
    )
    new_partner_nationality_id = fields.Many2one(
        'res.country',
        string='Nationality',
        help='Nationality or country of the new guest.',
    )

    property_id = fields.Many2one(
        'hospitality.property',
        string='Property',
        required=True,
        help='Property where the walk-in stay is registered.',
    )
    space_type_id = fields.Many2one(
        'hospitality.space.type',
        string='Room Type',
        required=True,
        help='Selected room or room category.',
    )
    space_id = fields.Many2one(
        'hospitality.space',
        string='Room',
        required=True,
        help='Assigned room or room for the walk-in guest.',
    )
    rate_code_id = fields.Many2one(
        'hospitality.rate.code',
        string='Rate Code',
        required=True,
        help='Rate code applied to the walk-in stay.',
    )
    arrival_time = fields.Float(
        string='Arrival Time',
        help='Expected arrival time.',
    )
    arrival = fields.Date(
        string='Arrival',
        default=fields.Date.context_today,
        help='Arrival date for the stay.',
    )
    expected_departure = fields.Date(
        string='Expected Departure',
        required=True,
        help='Expected departure date for the stay.',
    )
    adults = fields.Integer(
        string='Adults',
        default=1,
        help='Number of adult guests.',
    )
    children = fields.Integer(
        string='Children',
        default=0,
        help='Number of child guests.',
    )

    payment_method = fields.Selection(
        [
            ('cash', 'Cash'),
            ('card', 'Card'),
        ],
        string='Payment Method',
        required=True,
        help='Payment method selected for the walk-in deposit.',
    )
    deposit_amount = fields.Monetary(
        string='Deposit Amount',
        currency_field='currency_id',
        help='Initial deposit amount paid by the guest.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help='Currency for the deposit amount.',
    )

    @api.onchange('mode')
    def _onchange_mode(self):
        """Reset guest fields when switching guest source."""
        if self.mode == 'new_partner':
            self.partner_id = False
        else:
            self.new_partner_name = False
            self.new_partner_email = False
            self.new_partner_phone = False
            self.new_partner_nationality_id = False

    @api.onchange('property_id')
    def _onchange_property_id(self):
        """Clear the selected room when it belongs to another property."""
        if self.space_id and self.space_id.property_id != self.property_id:
            self.space_id = False

    def _get_or_create_partner(self):
        """Return the selected guest or create a new guest record."""
        self.ensure_one()
        if self.mode == 'existing_partner':
            if not self.partner_id:
                raise UserError(
                    'Please select an existing guest, or switch to '
                    '"New Guest" mode.'
                )
            return self.partner_id

        if not self.new_partner_name:
            raise UserError(
                'Please enter the new guest\'s name.'
            )
        partner_vals = {
            'name': self.new_partner_name,
            'email': self.new_partner_email,
            'phone': self.new_partner_phone,
            'is_guest' : True,
        }
        Partner = self.env['res.partner']
        if self.new_partner_nationality_id \
                and 'nationality_id' in Partner._fields:
            partner_vals['nationality_id'] = self.new_partner_nationality_id.id
        elif self.new_partner_nationality_id \
                and 'country_id' in Partner._fields:
            partner_vals['country_id'] = self.new_partner_nationality_id.id
        return Partner.create(partner_vals)

    def _prepare_reservation_vals(self, partner):
        """Prepare reservation values for the walk-in guest."""
        self.ensure_one()
        Reservation = self.env['hospitality.reservation']
        vals = {
            'partner_id': partner.id,
            'property_id': self.property_id.id,
            'space_type_id': self.space_type_id.id,
            'rate_code_id': self.rate_code_id.id,
            'adults': self.adults,
            'children': self.children,
        }
        if 'space_id' in Reservation._fields:
            vals['space_id'] = self.space_id.id
        if 'arrival' in Reservation._fields:
            vals['arrival'] = self.arrival
        if 'departure' in Reservation._fields:
            vals['departure'] = self.expected_departure
        if 'arrival_time' in Reservation._fields:
            vals['arrival_time'] = self.arrival_time
        if 'deposit_amount' in Reservation._fields:
            vals['deposit_amount'] = self.deposit_amount
        if 'is_walkin' in Reservation._fields:
            vals['is_walkin'] = True
        if 'created_via' in Reservation._fields:
            vals['created_via'] = 'front_desk'
        source_field = Reservation._fields.get('source')
        if source_field and source_field.selection:
            options = [key for key, _label in source_field.selection]
            if 'walk_in' in options:
                vals['source'] = 'walk_in'
        return vals

    def action_walk_in(self):
        """Create and check in a walk-in reservation.

            Creates or reuses a guest profile, creates the reservation,
            confirms it, performs check-in, and ensures an open folio
            exists for the stay.
            """
        self.ensure_one()

        partner = self._get_or_create_partner()

        Reservation = self.env['hospitality.reservation']
        reservation = Reservation.create(
            self._prepare_reservation_vals(partner)
        )

        if hasattr(reservation, 'action_confirm'):
            reservation.action_confirm()
        elif 'state' in Reservation._fields:
            reservation.write({'state': 'confirmed'})

        checkin_wizard = self.env['hospitality.front.desk.check.in.wizard'].create({
            'reservation_id': reservation.id,
            'space_id': self.space_id.id,
            'expected_departure': self.expected_departure,
            'deposit_amount': self.deposit_amount,
            'payment_method': self.payment_method,
            'print_reg_card': False,
        })
        checkin_wizard.action_check_in()

        self._ensure_open_folio(reservation)

        return {'type': 'ir.actions.act_window_close'}


    def _get_folio(self, reservation):
        """Look up the reservation's folio.

        hospitality.reservation carries no forward pointer to
        hospitality.folio — the relationship is one-way, held on
        hospitality.folio.reservation_id — so existence must always be
        checked via a reverse search, never via getattr() on the
        reservation.
        """
        Folio = self.env.get('hospitality.folio')
        if Folio is None or 'reservation_id' not in Folio._fields:
            return Folio.browse() if Folio is not None else False
        return Folio.search([('reservation_id', '=', reservation.id)], limit=1)

    def _ensure_open_folio(self, reservation):
        """Open a folio for the reservation if check-in didn't already
        create one (FD-04 acceptance: walk-in must yield a checked-in
        reservation *with an open folio*).

        Written schema-agnostically against hospitality.folio, since the
        exact set of fields it exposes beyond reservation_id is not
        guaranteed.
        """
        existing = self._get_folio(reservation)
        if existing:
            return existing

        Folio = self.env.get('hospitality.folio')
        if Folio is None:
            return

        folio_vals = {}
        if 'reservation_id' in Folio._fields:
            folio_vals['reservation_id'] = reservation.id
        if 'partner_id' in Folio._fields:
            folio_vals['partner_id'] = reservation.partner_id.id
        if 'property_id' in Folio._fields:
            folio_vals['property_id'] = reservation.property_id.id
        if 'currency_id' in Folio._fields:
            folio_vals['currency_id'] = self.currency_id.id

        state_field = Folio._fields.get('state')
        if state_field and state_field.selection:
            options = [key for key, _label in state_field.selection]
            for candidate in ('open', 'in_progress', 'draft'):
                if candidate in options:
                    folio_vals['state'] = candidate
                    break

        return Folio.create(folio_vals)