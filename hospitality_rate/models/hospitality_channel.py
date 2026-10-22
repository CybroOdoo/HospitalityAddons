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

class HospitalityChannel(models.Model):
    """
    Represents a distribution channel (OTA, direct, GDS, etc.) for hospitality inventory.
    Stub implementation for future channel management.
    """
    _name = 'hospitality.channel'
    _description = 'Hospitality Distribution Channel (Stub)'
    _order = 'name'

    name = fields.Char(
        string='Channel Name',
        required=True,
        help="Display name of the channel (e.g., 'Booking.com', 'Direct Website').",
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Uncheck to hide channel from active operations and selections.",
    )