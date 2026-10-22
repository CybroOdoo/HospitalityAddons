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

class HospitalityMixinBusinessDate(models.AbstractModel):
    """Business-date awareness mixin.

    Provides helpers so that any model can resolve the current business date
    for a property rather than relying on wall-clock date.  This is critical
    for night-audit correctness.
    """
    _name = 'hospitality.mixin.business.date'
    _description = 'Business-date awareness mixin'

    def _business_date_field(self):
        """Return the name of the date field on the inheriting model.
        Override in subclasses if the field is named differently.
        :returns str: field name, default 'business_date'.
        """
        return 'business_date'

    @api.model
    def _get_business_date(self, property_id):
        """Return the current business date for a property.

        :param property_id: int or hospitality.property record.
        :returns date: The property's business_date, or today() as fallback.
        """
        today = fields.Date.today()
        if not property_id:
            return today
        if isinstance(property_id, int):
            prop = self.env['hospitality.property'].browse(property_id)
        else:
            prop = property_id
        if not prop.exists():
            return today
        return prop.business_date or today
