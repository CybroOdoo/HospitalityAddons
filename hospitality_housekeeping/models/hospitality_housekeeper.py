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
from odoo import fields, models


class HospitalityHousekeeper(models.Model):
    """Staff member who performs housekeeping tasks but may not have
    an Odoo user account of their own (e.g. contract/agency staff)."""
    _name = 'hospitality.housekeeper'
    _description = 'Housekeeper'
    _order = 'name'

    name = fields.Char(required=True,string='Name',help="Full name of the housekeeper. This is the primary identifier "
             "for the staff member in housekeeping operations.",)
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  help="Optional link to the HR employee record. This connects the "
                                       "housekeeper to the broader HR system for payroll, benefits, "
                                       "and personnel management. May be empty for contract or "
                                       "agency staff who do not have a formal employee record.",
                                  )
    property_id = fields.Many2one(
        'hospitality.property', string='Property', required=True,
        help="The hospitality property where this housekeeper is assigned "
             "and performs their daily tasks.",
    )
    daily_credit_target = fields.Integer(
        string='Daily Credit Target', default=20,
        help='Target workload credits this housekeeper is expected '
             'to clear in a single business day.')
    active = fields.Boolean(default=True,
                            help="Indicates whether this housekeeper is currently active. "
                                 "Inactive housekeepers are hidden from most operations "
                                 "but their historical records are preserved.",
                            )