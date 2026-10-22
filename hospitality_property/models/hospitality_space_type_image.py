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
"""Gallery images for a space type.

The space type is the SALES unit: the booking engine searches it, rate
plans are keyed on it, and a reservation's ``space_type_id`` is required
while ``space_id`` is filled only when a room is actually assigned. A
guest therefore shops a category, and a category does not sell on one
photograph - it sells on the bed, the bathroom, the view and the floor
plan.

``image`` on hospitality.space.type stays as the single COVER, which the
booking engine results card and the kanban read. This model holds the
rest, in a defined order.

Same shape as hospitality.property.image: ``image.mixin`` carries the
resized variants as stored attachments, so a gallery thumbnail never
ships the full-resolution file.
"""
from odoo import fields, models


class HospitalitySpaceTypeImage(models.Model):
    """One image in a space type's gallery."""

    _name = 'hospitality.space.type.image'
    _description = 'Hospitality Room Type Image'
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    name = fields.Char(
        string='Title',
        required=True,
        help='Caption shown with the image, e.g. "King Bed" or "Bathroom".',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order the images appear in. Drag a card to change it.',
    )
    space_type_id = fields.Many2one(
        comodel_name='hospitality.space.type',
        string='Room Type',
        required=True,
        ondelete='cascade',
        index=True,
        help='Room type this image belongs to.',
    )
    # image.mixin declares image_1920 without a label; naming it here
    # keeps the upload widget from showing a bare "Image 1920".
    image_1920 = fields.Image(string='Image')
