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
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

_ASSET_CATEGORY_TO_WO_CATEGORY = {
    'it': 'it',
}


class HospitalityPpmTemplate(models.Model):
    """Defines a preventive maintenance schedule that periodically
    generates maintenance work orders for a specific asset or for all
    active assets belonging to a selected asset category."""
    _name = 'hospitality.ppm.template'
    _description = 'Hospitality Preventive Maintenance Template'
    _order = 'name'

    name = fields.Char(required=True)
    asset_category = fields.Selection([
        ('equipment', 'Equipment'),
        ('fixture', 'Fixture'),
        ('furniture', 'Furniture'),
        ('vehicle', 'Vehicle'),
        ('it', 'IT'),
        ('other', 'Other'),
    ])
    asset_id = fields.Many2one(
        'hospitality.asset',
        help="Leave empty to apply to every active asset in the selected "
             "category.")
    frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('custom_days', 'Custom (Days)'),
    ], required=True)
    custom_days = fields.Integer(
        help="Number of days between runs. Used only when Frequency is "
             "'Custom (Days)'.")
    task_template_text = fields.Text(
        help="Copied into the generated work order's Description.")
    last_run_at = fields.Datetime()
    next_run_at = fields.Datetime(
        compute='_compute_next_run_at', store=True, index=True)
    active = fields.Boolean(default=True)

    def _get_frequency_delta(self):
        """Return the date interval corresponding to the configured
        maintenance frequency."""
        self.ensure_one()
        mapping = {
            'daily': relativedelta(days=1),
            'weekly': relativedelta(weeks=1),
            'monthly': relativedelta(months=1),
            'quarterly': relativedelta(months=3),
            'semi_annual': relativedelta(months=6),
            'annual': relativedelta(years=1),
            'custom_days': relativedelta(days=self.custom_days or 0),
        }
        return mapping.get(self.frequency, relativedelta())

    @api.depends('frequency', 'custom_days', 'last_run_at')
    def _compute_next_run_at(self):
        """Compute the next scheduled execution time based on the last
        run timestamp and configured maintenance frequency."""
        for tmpl in self:
            if not tmpl.last_run_at:
                tmpl.next_run_at = tmpl.create_date or fields.Datetime.now()
            else:
                tmpl.next_run_at = tmpl.last_run_at + tmpl._get_frequency_delta()

    def _prepare_work_order_vals(self, asset):
        """Prepare the values required to create a preventive
        maintenance work order for the given asset."""
        wo_category = _ASSET_CATEGORY_TO_WO_CATEGORY.get(
            asset.category, 'general')
        return {
            'property_id': asset.property_id.id,
            'space_id': asset.space_id.id,
            'asset_id': asset.id,
            'category': wo_category,
            'source': 'ppm',
            'description': self.task_template_text or self.name,
        }

    @api.model
    def _cron_run_ppm_templates(self):
        """Daily cron entry point: create work orders for due templates.

        Assumption: a template scoped to a specific asset_id creates one
        work order for that asset. A category-wide template (asset_id
        empty) has no property_id of its own to put on a work order, so it
        fans out to one work order per active asset currently in that
        category — not a single ownerless work order.
        """
        WorkOrder = self.env['hospitality.work.order']
        due_templates = self.search([
            ('active', '=', True),
            ('next_run_at', '<=', fields.Datetime.now()),
        ])
        for tmpl in due_templates:
            if tmpl.asset_id:
                assets = tmpl.asset_id
            elif tmpl.asset_category:
                assets = self.env['hospitality.asset'].search([
                    ('active', '=', True),
                    ('category', '=', tmpl.asset_category),
                ])
            else:
                assets = self.env['hospitality.asset']

            for asset in assets:
                WorkOrder.create(tmpl._prepare_work_order_vals(asset))

            tmpl.last_run_at = fields.Datetime.now()