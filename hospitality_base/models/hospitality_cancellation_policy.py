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

class HospitalityCancellationPolicy(models.Model):
    """Manage cancellation policies for hospitality reservations."""
    _name = 'hospitality.cancellation.policy'
    _description = 'Hospitality Cancellation Policy'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True,help="Name of Cancellation Policy")
    code = fields.Char(string='Code', size=16, required=True, index=True,help="Code of Cancellation Policy")
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        help='Leave empty for a global policy.',
    )
    description = fields.Text(string='Description',help="Description of Cancellation Policy")
    active = fields.Boolean(string='Active', default=True,help="Whether this policy is active.")
    rule_ids = fields.One2many(
        comodel_name='hospitality.cancellation.policy.rule',
        inverse_name='policy_id',
        string='Rules',
        help="The policy rules associated with this policy.",
    )

    @api.constrains('code','property_id')
    def _check_code_unique(self):
        """Ensure the Cancellation policy code is unique."""
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
                    "Cancellation policy code '%s' must be unique per property."
                    % policy.code
                )


class HospitalityCancellationPolicyRule(models.Model):
    """Define charge rules for a cancellation policy."""
    _name = 'hospitality.cancellation.policy.rule'
    _description = 'Cancellation Policy Rule'
    _order = 'sequence, hours_before_arrival desc, days_before_arrival desc'

    policy_id = fields.Many2one(
        comodel_name='hospitality.cancellation.policy',
        string='Policy',
        required=True,
        ondelete='cascade',
        help="Cancellation Policy Rules",
    )
    sequence = fields.Integer(string='Sequence', default=10)
    hours_before_arrival = fields.Integer(
        string='Hours Before Arrival',
        default=0,
        help='Number of hours before arrival this rule applies from.',
    )
    days_before_arrival = fields.Integer(
        string='Days Before Arrival',
        default=0,
        help='Number of days before arrival this rule applies from.',
    )
    charge_type = fields.Selection(
        selection=[
            ('percent', 'Percentage of Total'),
            ('nights', 'Number of Nights'),
            ('fixed', 'Fixed Amount'),
        ],
        string='Charge Type',
        required=True,
        help="Charge Type for the cancellation policy.",
    )
    charge_value = fields.Float(
        string='Charge Value',
        required=True,
        default=0.0,
        help="Value charged for this cancellation policy.",
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        help='Required when charge type is Fixed Amount.',
    )

    @api.constrains('hours_before_arrival', 'days_before_arrival')
    def _check_lead_time(self):
        """Exactly one of hours or days must be > 0."""
        for rule in self:
            h = rule.hours_before_arrival or 0
            d = rule.days_before_arrival or 0
            if (h > 0) == (d > 0):
                raise ValidationError(
                    "Rule '%s': exactly one of 'Hours Before Arrival' or "
                    "'Days Before Arrival' must be greater than zero."
                    % (rule.policy_id.name or '')
                )

    @api.constrains('charge_type', 'charge_value')
    def _check_charge_value(self):
        """The charge value must be greater than or equal to 0"""
        for rule in self:
            if rule.charge_value < 0:
                raise ValidationError(
                    "Charge value must be ≥ 0 (rule on policy '%s')."
                    % (rule.policy_id.name or '')
                )
            if rule.charge_type == 'percent' and rule.charge_value > 100:
                raise ValidationError(
                    "Percentage charge value cannot exceed 100 "
                    "(rule on policy '%s')." % (rule.policy_id.name or '')
                )

    def _lead_time_hours(self):
        """Return the rule's lead time threshold in hours."""
        self.ensure_one()
        if self.hours_before_arrival:
            return self.hours_before_arrival
        return self.days_before_arrival * 24

    def compute_charge(self, total_amount, arrival_dt, cancel_dt):
        """Pick the applicable rule and return the cancellation charge.

        Selects the rule whose lead-time threshold is the largest value
        still ≤ the actual lead time between cancel_dt and arrival_dt.

        :param float total_amount: Full reservation value.
        :param datetime arrival_dt: Arrival datetime.
        :param datetime cancel_dt: Cancellation datetime.
        :returns float: Charge amount in the policy/currency's terms.
        """
        if not self:
            return 0.0
        delta = arrival_dt - cancel_dt
        actual_hours = delta.total_seconds() / 3600.0
        rules = self.sorted(key=lambda r: r._lead_time_hours(), reverse=True)
        applicable = None
        for rule in rules:
            if rule._lead_time_hours() <= actual_hours:
                applicable = rule
                break
        if not applicable:
            return 0.0
        if applicable.charge_type == 'percent':
            return total_amount * (applicable.charge_value / 100.0)
        elif applicable.charge_type == 'fixed':
            return applicable.charge_value
        else:
            return total_amount * applicable.charge_value
