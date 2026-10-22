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
from odoo.exceptions import AccessError

class HospitalityMixinProperty(models.AbstractModel):
    """Property scoping mixin.

    Inherit this mixin on any operational model that must be scoped to a
    single hospitality property.  It adds ``property_id``, enforces that the
    creating/writing user is allowed to work on that property, and exposes
    helpers for domain building.
    """
    _name = 'hospitality.mixin.property'
    _description = 'Property scoping mixin'

    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        required=True,
        index=True,
        ondelete='restrict',
        default=lambda self: self._default_property_id(),
        help="The property to scope to.",
    )

    def _default_property_id(self):
        """Return the property from context or fall back to user's current property."""
        ctx_id = self.env.context.get('default_property_id')
        if ctx_id:
            return ctx_id
        return self.env.user.property_id.id or False

    @api.model
    def _get_property_domain(self, user=None):
        """Return a domain that restricts records to the user's properties.
    Every user is scoped by their explicitly allowed properties.
        :param user: res.users record; defaults to self.env.user.
        :returns list: Odoo domain list.
        """
        user = user or self.env.user
        is_corporate = user.has_group(
            'hospitality_base.group_hospitality_corporate'
        )
        if is_corporate:
            return []
        allowed_ids = user.property_ids.ids
        if not allowed_ids:
            return [('id', '=', False)]
        return [('property_id', 'in', allowed_ids)]

    @api.constrains('property_id')
    def _check_property_access(self):
        """Ensure the user is allowed to create/write records on this property.
        Superusers bypass this check.
        """
        if self.env.su:
            return
        user = self.env.user
        allowed_ids = user.property_ids.ids
        for rec in self:
            if rec.property_id and rec.property_id.id not in allowed_ids:
                raise AccessError(
                    "You are not allowed to create or modify records for "
                    "property '%s'. Contact your administrator to get access."
                    % rec.property_id.display_name
                )
