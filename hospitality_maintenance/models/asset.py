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
from odoo.tools import _
from odoo.exceptions import ValidationError


class HospitalityAsset(models.Model):
    """Represents a maintainable asset within a property, including
    its location, hierarchy, preventive maintenance template, and
    associated work order history."""
    _name = 'hospitality.asset'
    _description = 'Hospitality Maintenance Asset'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(size=24, required=True, index=True)
    property_id = fields.Many2one(
        'hospitality.property', required=True, index=True)
    # Explicit string: see the note on work_order.space_id.
    space_id = fields.Many2one('hospitality.space', string='Room')
    category = fields.Selection([
        ('equipment', 'Equipment'),
        ('fixture', 'Fixture'),
        ('furniture', 'Furniture'),
        ('vehicle', 'Vehicle'),
        ('it', 'IT'),
        ('other', 'Other'),
    ], required=True)
    manufacturer = fields.Char()
    model = fields.Char()
    serial_no = fields.Char()
    install_date = fields.Date()
    warranty_until = fields.Date()
    ppm_template_id = fields.Many2one('hospitality.ppm.template')
    parent_asset_id = fields.Many2one(
        'hospitality.asset', ondelete='restrict',
        domain="[('property_id', '=', property_id), ('id', '!=', id)]")
    child_asset_ids = fields.One2many(
        'hospitality.asset', 'parent_asset_id', string='Sub-Assets')
    work_order_ids = fields.One2many(
        'hospitality.work.order', 'asset_id', string='Work Orders')
    work_order_count = fields.Integer(
        compute='_compute_work_order_count')
    # fields.Image rather than the plain Binary used by lost & found:
    # it validates that the upload is an image and caps the stored size,
    # which matters for a nameplate shot taken on a phone.
    photo = fields.Image(
        string='Photo',
        max_width=1024,
        max_height=1024,
        help='Identification shot - nameplate, serial label, or the asset '
             'in its installed position.',
    )
    notes = fields.Html()
    active = fields.Boolean(default=True)

    @api.depends('work_order_ids')
    def _compute_work_order_count(self):
        """Compute the number of work orders associated with each
        asset."""
        for rec in self:
            rec.work_order_count = len(rec.work_order_ids)

    @api.constrains('parent_asset_id')
    def _check_parent_cycles(self):
        """Prevent circular parent-child relationships in the asset
        hierarchy."""
        for rec in self:
            current = rec.parent_asset_id
            visited = set()
            while current:
                if current.id in visited or current.id == rec.id:
                    raise ValidationError(_(
                        "Circular reference detected in the asset "
                        "hierarchy for asset \"%s\".") % rec.name)
                visited.add(current.id)
                current = current.parent_asset_id