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

class HospitalitySpaceType(models.Model):
    """Inventory category describing a class of bookable spaces.

    ``property_id`` is optional here:
    * ``property_id = False``  → the type is global and available to every
      property.
    * ``property_id = <some property>`` → the type is private to that property.

    ``code`` uniqueness is enforced *per property_id* (NULL-safe at the
    application level via ``@api.constrains``; the SQL constraint handles the
    non-NULL case).

    NOTE: ``base_rate_id`` is intentionally stored as a Char placeholder until
    the ``hospitality.rate.code`` model is introduced in RATE-02.  It will be
    migrated to a Many2one at that point.
    """
    _name = 'hospitality.space.type'
    _description = 'Room Type'
    _inherit = ['hospitality.mixin.property']
    _order = 'sequence, name'

    name = fields.Char(
        string='Room Type',
        required=True,
        translate=True,
        help="Name of Room Type",
    )
    code = fields.Char(
        string='Code',
        size=16,
        required=True,
        index=True,
        help="Code for Room Type",
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        ondelete='restrict',
        index=True,
        help='Leave empty to make this room type available to all properties.',
    )
    category = fields.Selection(
        selection=[
            ('room', 'Room'),
            ('suite', 'Suite'),
            ('dorm_bed', 'Dorm Bed'),
            ('vacation_unit', 'Vacation Unit'),
            ('parking', 'Parking'),
            ('meeting', 'Meeting Room'),
            ('cabana', 'Cabana'),
            ('other', 'Other'),
        ],
        string='Category',
        required=True,
        default='room',
        help="Category of Room Type",
    )
    default_occupancy = fields.Integer(
        string='Default Occupancy',
        required=True,
        default=2,
        help="The default occupancy for this room type",
    )
    max_occupancy = fields.Integer(
        string='Max Occupancy',
        required=True,
        default=2,
        help="The maximum occupancy for this room type",
    )
    base_rate_id = fields.Char(
        string='Base Rate Code',
        help='Placeholder — will become Many2one(hospitality.rate.code) in RATE-02.',
    )
    amenity_ids = fields.Many2many(
        comodel_name='hospitality.space.feature',
        relation='space_type_feature_rel',
        column1='space_type_id',
        column2='feature_id',
        string='Amenities / Features',
        help="The features of this room type",
    )
    bed_config = fields.Selection(
        selection=[
            ('single', 'Single'),
            ('twin', 'Twin'),
            ('double', 'Double'),
            ('queen', 'Queen'),
            ('king', 'King'),
            ('bunk', 'Bunk'),
            ('mixed', 'Mixed'),
        ],
        string='Bed Configuration',
        help="The bed configuration for this room type",
    )
    smoking = fields.Boolean(
        string='Smoking Allowed',
        default=False,
        help="If enabled,smoking is allowed.",
    )
    size_sqm = fields.Float(
        string='Size (sqm)',
        digits=(10, 2),
        help="The size of room in sqm.",
    )
    description = fields.Html(
        string='Description',
        help="Description of Room Type",
    )
    image = fields.Image(
        string='Cover Image',
        max_width=1024,
        max_height=1024,
        help="The one representative shot. The booking engine results "
             "card and the kanban read this field.",
    )
    image_ids = fields.One2many(
        comodel_name='hospitality.space.type.image',
        inverse_name='space_type_id',
        string='Images',
        copy=True,
        help="Gallery for the room category - bed, bathroom, view, floor "
             "plan. Ordered by the sequence on each image.",
    )
    image_count = fields.Integer(
        string='Image Count',
        compute='_compute_image_count',
        help="Number of gallery images, excluding the cover.",
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Sequence of Room Type",
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Whether this Room Type is active or not.",
    )

    @api.depends('image_ids')
    def _compute_image_count(self):
        """How many gallery images the space type carries."""
        counts = dict(self.env['hospitality.space.type.image']._read_group(
            [('space_type_id', 'in', self.ids)],
            groupby=['space_type_id'], aggregates=['__count'],
        ))
        for space_type in self:
            space_type.image_count = counts.get(space_type, 0)

    @api.constrains('code', 'property_id')
    def _check_code_unique_per_property(self):
        """
        Enforce code uniqueness per property_id (non-null case).
        The null/global case is handled by _check_code_unique_global below.
        """
        for rec in self:
            if rec.property_id:
                domain = [
                    ('property_id', '=', rec.property_id.id),
                    ('code', '=', rec.code),
                    ('id', '!=', rec.id),
                ]
                if self.search_count(domain):
                    raise ValidationError(
                        'Room type code "%s" already exists for this property.' % rec.code
                    )

    @api.constrains('default_occupancy', 'max_occupancy')
    def _check_occupancy(self):
        """Ensure that default_occupancy >= 1 and max_occupancy >= default_occupancy."""
        for rec in self:
            if rec.default_occupancy < 1:
                raise ValidationError(
                    'Default occupancy must be at least 1 '
                    '(got %d for "%s").' % (rec.default_occupancy, rec.name)
                )
            if rec.max_occupancy < rec.default_occupancy:
                raise ValidationError(
                    'Max occupancy (%d) cannot be less than default occupancy '
                    '(%d) for "%s".' % (
                        rec.max_occupancy, rec.default_occupancy, rec.name
                    )
                )

    @api.constrains('code', 'property_id')
    def _check_code_unique_global(self):
        """Enforce code uniqueness among global types (property_id IS NULL).

        The SQL constraint covers non-NULL property pairs; this method
        handles records where property_id is False / NULL.
        """
        for rec in self:
            if not rec.property_id:
                domain = [
                    ('property_id', '=', False),
                    ('code', '=', rec.code),
                    ('id', '!=', rec.id),
                ]
                if self.search_count(domain):
                    raise ValidationError(
                        'Global room type code "%s" already exists.' % rec.code
                    )

    def action_archive_space_type(self):
        """Archive space type."""
        self.write({'active': False})

    def action_unarchive_space_type(self):
        """Unarchive space type."""
        self.write({'active': True})
