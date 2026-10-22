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
from odoo.exceptions import ValidationError, UserError
from datetime import date

class HospitalitySpace(models.Model):
    """Individual bookable space (room, suite, etc.) with operational status.

    The ``status`` field implements a state machine controlling housekeeping
    and availability workflow.  Out-of-order (OOO) and out-of-service (OOS)
    windows are managed via dedicated wizards accessible to property managers.

    TERMINOLOGY: the user interface says "Room" everywhere - labels, help
    texts, menus, messages and reports. The model, table, fields and
    xmlids deliberately keep ``space``/``space_type``, because renaming
    them would mean a schema migration and would break every external
    reference for no functional gain. If you are reading ``space_id`` in
    code and "Room" on screen, that is intended and they are the same
    thing.
    """
    _name = 'hospitality.space'
    _description = 'Hospitality Room'
    _inherit = ['hospitality.mixin.property', 'mail.thread']
    _order = 'property_id, code'

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
        help="Name of the room",
    )
    code = fields.Char(
        string='Code',
        size=16,
        required=True,
        index=True,
        tracking=True,
        help="Code of the room",
    )
    space_type_id = fields.Many2one(
        comodel_name='hospitality.space.type',
        string='Room Type',
        required=True,
        ondelete='restrict',
        tracking=True,
        help="Type of the room",
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        required=True,
        index=True,
        tracking=True,
        help="The property to which this room belong to."
    )

    building_id = fields.Many2one(
        comodel_name='hospitality.building',
        string='Building',
        ondelete='restrict',
        tracking=True,
        help="The building to which this room belong to."
    )
    floor_id = fields.Many2one(
        comodel_name='hospitality.floor',
        string='Floor',
        ondelete='restrict',
        tracking=True,
        help="The floor to which this room belong to."
    )
    section_id = fields.Many2one(
        comodel_name='hospitality.section',
        string='Section',
        ondelete='restrict',
        tracking=True,
        help="The section to which this room belong to."
    )
    bed_count = fields.Integer(
        string='Bed Count',
        default=1,
        help="Number of beds in this room.",
    )
    feature_ids = fields.Many2many(
        comodel_name='hospitality.space.feature',
        relation='space_feature_rel',
        column1='space_id',
        column2='feature_id',
        string='Features',
        help='Overrides/extends type amenities for this specific room.',
    )
    parent_space_id = fields.Many2one(
        comodel_name='hospitality.space',
        string='Parent Room',
        ondelete='restrict',
        help='Parent connecting room',
        domain="[('property_id', '=', property_id), ('id', '!=', id)]",
    )
    child_space_ids = fields.One2many(
        comodel_name='hospitality.space',
        inverse_name='parent_space_id',
        string='Connected Rooms',
        help="The rooms connected to this room",
    )
    lock_parent_when_child_booked = fields.Boolean(
        string='Lock Parent When Child Booked',
        default=False,
        help='If enabled, booking this room will also block the parent.',
    )
    is_virtual = fields.Boolean(
        string='Virtual Room',
        default=False,
        help='Pseudo room (e.g., House Use) - not a physical room.',
    )
    status = fields.Selection(
        selection=[
            ('vacant_clean', 'Vacant Clean'),
            ('vacant_dirty', 'Vacant Dirty'),
            ('occupied_clean', 'Occupied Clean'),
            ('occupied_dirty', 'Occupied Dirty'),
            ('inspected', 'Inspected'),
            ('pickup', 'Pickup'),
            ('ooo', 'Out of Order'),
            ('oos', 'Out of Service'),
        ],
        string='Status',
        required=True,
        default='vacant_clean',
        tracking=True,
        help="Status of this room",
    )
    ooo_reason = fields.Text(
        string='Out of Order Reason',
        help='Out of Order Reason',
    )
    ooo_from = fields.Date(
        string='Out of Order From',
        help="Out of Order From",
    )
    ooo_to = fields.Date(
        string='Out of Order To',
        help="Out of Order To"
    )
    oos_reason = fields.Text(
        string='Out of Service Reason',
        help="Out of Service Reason"
    )
    oos_from = fields.Date(
        string='Out of Service From',
        help="Out of Service Form"
    )
    oos_to = fields.Date(
        string='Out of Service To',
        help="Out of Service To"
    )
    color = fields.Integer(
        string='Color',
        compute='_compute_color',
        store=False,
        help='Kanban color based on status.',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Whether this room is active or not.",
    )

    @api.constrains('code', 'property_id')
    def _check_code_unique_per_property(self):
        """Enforce code uniqueness per property (application-level check)."""
        for rec in self:
            domain = [
                ('property_id', '=', rec.property_id.id),
                ('code', '=', rec.code),
                ('id', '!=', rec.id),
            ]
            if self.search_count(domain):
                raise ValidationError(
                    'Room code "%s" already exists for this property.' % rec.code
                )

    @api.constrains('parent_space_id')
    def _check_parent_cycles(self):
        """Prevent parent cycles and enforce max depth of 4."""
        for rec in self:
            if not rec.parent_space_id:
                continue
            visited = set()
            current = rec
            depth = 0
            while current.parent_space_id:
                if current.parent_space_id.id in visited:
                    raise ValidationError(
                        'Circular reference detected in connecting rooms for room "%s".' % rec.code
                    )
                visited.add(current.parent_space_id.id)
                current = current.parent_space_id
                depth += 1
                if depth > 4:
                    raise ValidationError(
                        'Maximum connecting room depth (4 levels) exceeded for room "%s".' % rec.code
                    )

    @api.constrains('status', 'ooo_from', 'ooo_to')
    def _check_ooo_dates(self):
        """Validate Out of Order date range when status is 'ooo'."""
        for rec in self:
            if rec.status == 'ooo':
                if not rec.ooo_from or not rec.ooo_to:
                    raise ValidationError(
                        'Out of Order date range is required when status is Out of Order.'
                    )
                if rec.ooo_from < date.today():
                    raise ValidationError(
                        'Out of Order start date cannot be in the past.'
                    )
                if rec.ooo_to < rec.ooo_from:
                    raise ValidationError(
                        'Out of Order end date must be after or equal to start date.'
                    )

    @api.constrains('status', 'oos_from', 'oos_to')
    def _check_oos_dates(self):
        """Validate Out of Service date range when status is 'oos'."""
        for rec in self:
            if rec.status == 'oos':
                if not rec.oos_from or not rec.oos_to:
                    raise ValidationError(
                        'Out of Service date range is required when status is Out of Service.'
                    )
                if rec.oos_from < date.today():
                    raise ValidationError(
                        'Out of Service start date cannot be in the past.'
                    )
                if rec.oos_to < rec.oos_from:
                    raise ValidationError(
                        'Out of Service end date must be after or equal to start date.'
                    )

    @api.constrains('space_type_id', 'property_id')
    def _check_space_type_property(self):
        """Ensure space type belongs to same property or is global."""
        for rec in self:
            if rec.space_type_id.property_id:
                if rec.space_type_id.property_id != rec.property_id:
                    raise ValidationError(
                        'Room type "%s" does not belong to property "%s".' % (
                            rec.space_type_id.name,
                            rec.property_id.name
                        )
                    )

    @api.depends('status')
    def _compute_color(self):
        """Map status to kanban color tokens."""
        color_map = {
            'vacant_clean': 10,
            'vacant_dirty': 3,
            'occupied_clean': 4,
            'occupied_dirty': 7,
            'inspected': 5,
            'pickup': 8,
            'ooo': 1,
            'oos': 9,
        }
        for rec in self:
            rec.color = color_map.get(rec.status, 0)

    @api.onchange('space_type_id')
    def _onchange_space_type_id(self):
        """Populate property from space type if set."""
        if self.space_type_id and self.space_type_id.property_id:
            self.property_id = self.space_type_id.property_id

    @api.onchange('building_id')
    def _onchange_building_id(self):
        if self.building_id:
            self.property_id = self.building_id.property_id
            if self.floor_id and self.floor_id.building_id != self.building_id:
                self.floor_id = False
                self.section_id = False
            return {
                'domain': {
                    'floor_id': [('building_id', '=', self.building_id.id)],
                    'section_id': [('building_id', '=', self.building_id.id)],
                }
            }
        self.floor_id = False
        self.section_id = False
        return {
            'domain': {
                'floor_id': [],
                'section_id': [],
            }
        }

    @api.onchange('property_id')
    def _onchange_property_id(self):
        """Filter building by property."""
        if self.property_id:
            return {
                'domain': {
                    'building_id': [('property_id', '=', self.property_id.id)],
                }
            }
        else:
            return {
                'domain': {
                    'building_id': [],
                }
            }

    def _set_status(self, target_status, allowed_from):
        """
        Internal helper for status transitions.

        :param target_status: Target status to set
        :param allowed_from: List of allowed source statuses
        :raises UserError: If transition is not allowed
        """
        self.ensure_one()
        if self.status not in allowed_from:
            status_labels = dict(self._fields['status'].selection)
            raise UserError(
                'Cannot transition from "%s" to "%s".\nAllowed sources: %s' % (
                    status_labels.get(self.status),
                    status_labels.get(target_status),
                    ', '.join([status_labels.get(s) for s in allowed_from])
                )
            )
        self.status = target_status

    def action_set_vacant_clean(self):
        """Set status to Vacant Clean (from vacant_dirty or inspected)."""
        for rec in self:
            rec._set_status('vacant_clean', ['vacant_dirty', 'inspected'])

    def action_set_vacant_dirty(self):
        """Set status to Vacant Dirty (from occupied_* or ooo/oos)."""
        for rec in self:
            rec._set_status('vacant_dirty', ['occupied_clean', 'occupied_dirty', 'ooo', 'oos'])

    def action_set_occupied_clean(self):
        """Set status to Occupied Clean (from vacant_clean or occupied_dirty)."""
        for rec in self:
            rec._set_status('occupied_clean', ['vacant_clean', 'occupied_dirty'])

    def action_set_occupied_dirty(self):
        """Set status to Occupied Dirty (from occupied_clean)."""
        for rec in self:
            rec._set_status('occupied_dirty', ['occupied_clean'])

    def action_set_inspected(self):
        """Set status to Inspected (from vacant_clean)."""
        for rec in self:
            rec._set_status('inspected', ['vacant_clean'])

    def action_set_pickup(self):
        """Set status to Pickup (from vacant_clean or vacant_dirty)."""
        for rec in self:
            rec._set_status('pickup', ['vacant_clean', 'vacant_dirty'])

    def action_open_ooo_wizard(self):
        """Open Out-of-Order wizard for selected spaces."""
        return {
            'name': 'Set Out of Order',
            'type': 'ir.actions.act_window',
            'res_model': 'hospitality.space.status.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_space_ids': [(6, 0, self.ids)],
                'default_mode': 'ooo',
            },
        }

    def action_release_ooo(self):
        """Release from out-of-order status → vacant_dirty."""
        for rec in self:
            if rec.status != 'ooo':
                raise UserError(
                    'Room "%s" is not in Out of Order status.' % rec.code
                )
            rec.write({
                'status': 'vacant_dirty',
                'ooo_reason': False,
                'ooo_from': False,
                'ooo_to': False,
            })

    def action_open_oos_wizard(self):
        """Open out-of-service wizard for selected spaces."""
        return {
            'name': 'Set Out of Service',
            'type': 'ir.actions.act_window',
            'res_model': 'hospitality.space.status.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_space_ids': [(6, 0, self.ids)],
                'default_mode': 'oos',
            },
        }

    def action_release_oos(self):
        """Release from out-of-service status → vacant_dirty."""
        for rec in self:
            if rec.status != 'oos':
                raise UserError(
                    'Room "%s" is not in Out of Service status.' % rec.code
                )
            rec.write({
                'status': 'vacant_dirty',
                'oos_reason': False,
                'oos_from': False,
                'oos_to': False,
            })

    def action_archive_space(self):
        """Archive space."""
        self.write({'active': False})

    def action_unarchive_space(self):
        """Unarchive space."""
        self.write({'active': True})
