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
from odoo.exceptions import UserError
from odoo.tools.translate import _


class HospitalityLinenCount(models.Model):
    """A single linen inventory count for a property on a given date,
    made up of one line per linen item counted. Draft counts can
    still be edited; posting locks in the count as the record of
    truth for that date."""
    _name = 'hospitality.linen.count'
    _description = 'Linen Count'
    _inherit = ['hospitality.mixin.property']
    _order = 'count_date desc'

    name = fields.Char(
        string='Name', compute='_compute_name', store=True,
        help='Readable label, e.g. "Demo Property Linen Count - '
             '07/06/2026".')
    property_id = fields.Many2one(
        'hospitality.property', string='Property', required=True,
        index=True)
    count_date = fields.Date(
        required=True, default=fields.Date.context_today)
    counted_by = fields.Many2one(
        'res.users', string='Counted By',
        default=lambda self: self.env.uid)
    line_ids = fields.One2many(
        'hospitality.linen.count.line', 'count_id', string='Lines')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], required=True, default='draft')

    @api.depends('property_id', 'count_date')
    def _compute_name(self):
        """Compute a descriptive name using the property and inventory
            count date."""
        for count in self:
            prop_name = count.property_id.display_name or _(
                'New Property')
            date_str = (
                fields.Date.to_string(count.count_date)
                if count.count_date else _('No Date'))
            count.name = f'{prop_name} Linen Count - {date_str}'

    def action_post(self):
        """draft -> posted. Requires at least one counted line."""
        for count in self:
            if count.state == 'posted':
                continue
            if not count.line_ids:
                raise UserError(_(
                    'Cannot post "%s" with no lines.') % count.name)
            count.state = 'posted'
        return True

    def action_reset_to_draft(self):
        """posted -> draft, for corrections."""
        return self.write({'state': 'draft'})


class HospitalityLinenCountLine(models.Model):
    """One counted linen item on a hospitality.linen.count."""
    _name = 'hospitality.linen.count.line'
    _description = 'Linen Count Line'
    _order = 'id'

    count_id = fields.Many2one(
        'hospitality.linen.count', string='Linen Count', required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string='Linen Item')
    expected_qty = fields.Float(string='Expected Qty')
    counted_qty = fields.Float(string='Counted Qty')
    variance_qty = fields.Float(
        string='Variance', compute='_compute_variance_qty', store=True,
        help='Counted minus expected. Negative means a shortage.')

    @api.depends('expected_qty', 'counted_qty')
    def _compute_variance_qty(self):
        """Compute the variance between the expected and counted
            quantities for each linen item."""
        for line in self:
            line.variance_qty = line.counted_qty - line.expected_qty