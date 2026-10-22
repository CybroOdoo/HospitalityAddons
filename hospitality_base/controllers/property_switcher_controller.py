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
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError

class PropertySwitcherController(http.Controller):

    @http.route(
        '/hospitality/property_data',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def get_property_data(self, **kwargs):
        """Return current user's allowed properties and current property."""
        user = request.env.user
        current = user.property_id
        properties = []
        for prop in user.property_ids.filtered('active'):
            properties.append({
                'id': prop.id,
                'name': prop.name,
                'code': prop.code,
                'business_date': str(prop.business_date) if prop.business_date else '',
            })
        return {
            'current_property_id': current.id if current else False,
            'properties': properties,
        }

    @http.route(
        '/hospitality/switch_property',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def switch_property(self, property_id=None, **kwargs):
        """Switch the current user's active property."""
        user = request.env.user
        if not property_id:
            return {'ok': False, 'error': 'No property_id provided.'}
        allowed_ids = user.property_ids.ids
        if property_id not in allowed_ids:
            raise AccessError(
                "Property (id=%d) is not in your list of allowed properties."
                % property_id
            )
        prop = request.env['hospitality.property'].browse(property_id)
        if not prop.exists() or not prop.active:
            return {'ok': False, 'error': 'Property not found or inactive.'}
        user.sudo().write({'property_id': property_id})
        return {
            'ok': True,
            'property_id': prop.id,
            'name': prop.display_name,
        }
