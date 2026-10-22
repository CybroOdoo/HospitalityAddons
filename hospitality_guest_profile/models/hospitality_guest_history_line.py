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
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC License
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class HospitalityGuestHistoryLine(models.Model):
    """One stay record linked to a guest (res.partner)."""
    _name = 'hospitality.guest.history.line'
    _description = 'Guest Stay History'
    _order = 'check_in desc, id desc'
    _rec_name = 'reservation_ref'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Guest',
        required=True,
        index=True,
        ondelete='cascade',
        help='Guest associated with this stay.',
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        index=True,
        ondelete='set null',
        help='Property where the guest stayed.',
    )
    reservation_ref = fields.Char(
        string='Reservation Ref',
        help='Stub reference populated until L3 (hospitality.reservation) ships.',
    )
    reservation_id = fields.Reference(
        selection=[('hospitality.reservation', 'Reservation')],
        string='Reservation',
        help='Populated by L3+ events when hospitality.reservation is present.',
    )
    check_in = fields.Date(string='Check-in',help="Date when the guest checked in")
    check_out = fields.Date(string='Check-out',help="Date when the guest checked out")
    nights = fields.Integer(
        string='Nights',
        compute='_compute_nights',
        store=True,
        help='Number of nights between the check-in and check-out dates.',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        ondelete='restrict',
        help='Currency used for the stay revenue amounts.',
    )
    revenue = fields.Monetary(
        string='Revenue',
        currency_field='currency_id',
        help='Total revenue generated from the stay.',
    )
    payment_revenue = fields.Monetary(
        string='Payment Revenue',
        currency_field='currency_id',
        help='Total payment revenue recorded for the stay.',
    )
    source_id = fields.Many2one(
        comodel_name='hospitality.source.code',
        string='Source',
        ondelete='set null',
        help='Source through which the reservation was acquired.',
    )
    segment_id = fields.Many2one(
        comodel_name='hospitality.market.segment',
        string='Market Segment',
        ondelete='set null',
        help='Market segment associated with the stay.',
    )
    rating = fields.Selection(
        selection=[
            ('1', '★'),
            ('2', '★★'),
            ('3', '★★★'),
            ('4', '★★★★'),
            ('5', '★★★★★'),
        ],
        string='Rating',
        help='Guest rating for the stay, from one to five stars.',
    )

    @api.depends('check_in', 'check_out')
    def _compute_nights(self):
        """Compute the number of nights from the stay dates."""
        for rec in self:
            if rec.check_in and rec.check_out and rec.check_out > rec.check_in:
                rec.nights = (rec.check_out - rec.check_in).days
            else:
                rec.nights = 0

    @api.constrains('check_in', 'check_out')
    def _check_in_and_out_dates(self):
        """Ensure check out date is not before check-in date."""
        for rec in self:
            if not rec.check_in or not rec.check_out:
                raise ValidationError(
                    'Check-in and check-out dates are required.'
                )
            if rec.check_out < rec.check_in:
                raise ValidationError(
                    'Check-out date must be after or equal to check-in date.'
                )

    @api.constrains('partner_id', 'check_in', 'check_out')
    def _check_overlapping_stays(self):
        """Prevent overlapping stay periods for the same guest."""
        for record in self:
            if not record.partner_id or not record.check_in or not record.check_out:
                continue
            overlapping = self.search([
                ('id', '!=', record.id),
                ('partner_id', '=', record.partner_id.id),
                ('check_in', '<', record.check_out),
                ('check_out', '>', record.check_in),
            ], limit=1)
            if overlapping:
                raise ValidationError(
                    "Guest '%s' already has a stay from %s to %s. "
                    "Stay dates cannot overlap."
                    % (
                        record.partner_id.name,
                        overlapping.check_in,
                        overlapping.check_out,
                    )
                )
