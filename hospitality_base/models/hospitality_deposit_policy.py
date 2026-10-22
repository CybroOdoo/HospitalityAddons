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
from odoo.exceptions import ValidationError

class HospitalityDepositPolicy(models.Model):
    _name = 'hospitality.deposit.policy'
    _description = 'Hospitality Deposit Policy'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True, help="Name of Deposit Policy")
    code = fields.Char(string='Code', size=16, required=True, index=True, help="Code of Deposit Policy")
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        help='Leave empty for a global policy.',
    )
    due_at = fields.Selection(
        selection=[
            ('booking', 'At Booking'),
            ('x_days_before_arrival', 'X Days Before Arrival'),
            ('arrival', 'At Arrival'),
        ],
        string='Due At',
        required=True,
        default='booking',
        help='Defines when the deposit payment is due.',
    )
    due_offset_days = fields.Integer(
        string='Days Before Arrival',
        default=0,
        help='Used when Due At = "X Days Before Arrival".',
    )
    amount_type = fields.Selection(
        selection=[
            ('percent_total', 'Percentage of Total'),
            ('first_night', 'First Night Amount'),
            ('fixed', 'Fixed Amount'),
        ],
        string='Amount Type',
        required=True,
        help='Defines how the deposit amount is calculated.',
    )
    amount_value = fields.Float(string='Amount Value', default=0.0,
                                help='Value used to calculate the deposit according to the selected amount type.',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        help='Required when amount type is Fixed Amount.',
    )
    description = fields.Text(string='Description',help='Additional details or notes about the deposit policy.',)
    active = fields.Boolean(string='Active', default=True,
                            help='Indicates whether this deposit policy is active and available for use.',
    )

    @api.constrains('code', 'property_id')
    def _check_code_unique(self):
        """Ensure the Deposit policy code is unique."""
        for policy in self:
            if not policy.code:
                continue
            duplicate = self.search([
                ('code', '=', policy.code),
                ('property_id', '=', policy.property_id.id),
                ('id', '!=', policy.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "Deposit policy code '%s' must be unique per property."
                    % policy.code
                )

    @api.constrains('due_at', 'due_offset_days')
    def _check_due_offset(self):
        """The due offset days must be positive"""
        for rec in self:
            if rec.due_at == 'x_days_before_arrival' and not (rec.due_offset_days > 0):
                raise ValidationError(
                    "Policy '%s': 'Days Before Arrival' must be > 0 when "
                    "'Due At' is set to 'X Days Before Arrival'." % rec.name
                )

    @api.constrains('amount_type', 'amount_value')
    def _check_amount_value(self):
        """The amount value must be always positive. """
        for rec in self:
            if rec.amount_value < 0:
                raise ValidationError(
                    "Policy '%s': amount value must be ≥ 0." % rec.name
                )
            if rec.amount_type == 'percent_total' and rec.amount_value > 100:
                raise ValidationError(
                    "Policy '%s': percentage amount cannot exceed 100." % rec.name
                )

    def compute_deposit(self, total_amount, first_night_amount):
        """Return the deposit amount for a reservation.

        :param float total_amount: Full reservation value.
        :param float first_night_amount: Value of the first night.
        :returns float: Deposit amount due.
        """
        self.ensure_one()
        if self.amount_type == 'percent_total':
            return total_amount * (self.amount_value / 100.0)
        elif self.amount_type == 'first_night':
            return first_night_amount
        elif self.amount_type == 'fixed':
            return self.amount_value
        return 0.0
