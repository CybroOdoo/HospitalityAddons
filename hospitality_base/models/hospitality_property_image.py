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
"""Gallery images for a hospitality property.

A property is not one picture. Exterior, lobby, a room, the pool and the
restaurant are all needed by the booking engine, confirmation emails and
the website, and they are needed in a defined order. ``property_image``
on hospitality.property stays as the single COVER image - the kanban card
and anything wanting one representative shot read that - and this model
holds the rest.

Shaped after Odoo's own ``product.image``: ``image.mixin`` carries the
resized variants (1920/1024/512/256/128) as stored attachments, so a
gallery thumbnail never ships the full-resolution file.
"""
from odoo import fields, models


class HospitalityPropertyImage(models.Model):
    """One image in a property's gallery."""

    _name = 'hospitality.property.image'
    _description = 'Hospitality Property Image'
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    name = fields.Char(
        string='Title',
        required=True,
        help='Caption shown with the image, e.g. "Lobby" or "Deluxe Suite".',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order the images appear in. Drag a card to change it.',
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        required=True,
        ondelete='cascade',
        index=True,
        help='Property this image belongs to.',
    )
    # image.mixin declares image_1920 without a label; naming it here
    # keeps the upload widget from showing a bare "Image 1920".
    image_1920 = fields.Image(string='Image')
