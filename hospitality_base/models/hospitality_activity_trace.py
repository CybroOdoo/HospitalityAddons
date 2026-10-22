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

class HospitalityActivityTrace(models.Model):
    """Model defined to store and manage hospitality activity traces."""
    _name = 'hospitality.activity.trace'
    _description = 'Hospitality Activity Trace'
    _order = 'create_date desc'
    _inherit = ['hospitality.mixin.property']

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        help='Automatically generated name based on the record type and the first 40 characters of its text.',
    )
    type = fields.Selection(
        selection=[
            ('arrival', 'Arrival'),
            ('departure', 'Departure'),
            ('in_house', 'In House'),
            ('anytime', 'Anytime'),
        ],
        string='Type',
        required=True,
        default='anytime',
        help='Defines when this activity trace is applicable: at arrival, departure, during the stay, or at any time.',
    )
    text = fields.Text(string='Trace Text', required=True,
                       help='Contains the activity trace or instruction to be recorded for the property or reservation.',
    )
    resolved = fields.Boolean(string='Resolved', default=False,
                              help='Indicates whether this activity trace has been resolved.',
    )
    resolved_by = fields.Many2one(
        comodel_name='res.users',
        string='Resolved By',
        readonly=True,
        copy=False,
        help='User who marked this activity trace as resolved.',
    )
    resolved_at = fields.Datetime(
        string='Resolved At',
        readonly=True,
        copy=False,
        help='Date and time when this activity trace was marked as resolved.',
    )
    create_uid = fields.Many2one(
        comodel_name='res.users',
        string='Created By',
        readonly=True,
        help='User who created this activity trace.',
    )
    create_date = fields.Datetime(
        string='Created On',
        readonly=True,
        help='Date and time when this activity trace was created.',
    )

    @api.depends('type', 'text')
    def _compute_name(self):
        """
        Compute the display name from the record type and text content.
        The computed name consists of the selected type label enclosed in
        brackets, followed by the first 40 characters of the text.
        """
        type_label = dict(self._fields['type'].selection)
        for rec in self:
            label = type_label.get(rec.type, rec.type or '')
            snippet = (rec.text or '')[:40]
            rec.name = '[%s] %s' % (label, snippet)

    def action_resolve(self):
        """Mark the trace as resolved."""
        for rec in self:
            rec.write({
                'resolved': True,
                'resolved_by': self.env.user.id,
                'resolved_at': fields.Datetime.now(),
            })
