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
import json
from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError, AccessError, UserError

class HospitalityRatePlan(models.Model):
    """
    Rate Plan defining pricing for a specific rate code and space type.

    Plans have date ranges, weekday masks, and various occupancy pricing models
    (flat rate, per pax, or occupancy grid). Includes audit trail and
    immutability controls for locked records.
    """
    _name = 'hospitality.rate.plan'
    _description = 'Hospitality Rate Plan'
    _order = 'rate_code_id, space_type_id, date_from'

    rate_code_id = fields.Many2one('hospitality.rate.code', string='Rate Code', required=True,
                                   ondelete='cascade', index=True,
                                   help="Rate code this plan belongs to. Deleting the rate code removes its plans.",
                                   )
    space_type_id = fields.Many2one('hospitality.space.type', string='Room Type', required=True,
                                    ondelete='restrict', help="Room type (room type) this plan applies to.", )
    property_id = fields.Many2one('hospitality.property', string='Property',
                                  related='rate_code_id.property_id', store=True, index=True, readonly=True,
                                  help="Property inherited from the rate code.",
                                  )
    date_from = fields.Date(string='Valid From', required=True, help="Start date of the rate plan validity period.", )
    date_to = fields.Date(string='Valid To', required=True, help="End date of the rate plan validity period.", )
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id,
                                  help="Currency used for all prices in this plan.",
                                  )
    price_single = fields.Monetary(string='Single Occupancy', currency_field='currency_id',
                                   help="Price for 1 adult occupancy."
                                   )
    price_double = fields.Monetary(string='Double Occupancy', currency_field='currency_id',
                                   help="Price for 2 adults occupancy (base rate).",
                                   )
    price_extra_adult = fields.Monetary(string='Extra Adult', currency_field='currency_id',
                                        help="Additional price per extra adult beyond double occupancy.",
                                        )
    price_extra_child = fields.Monetary(string='Extra Child', currency_field='currency_id',
                                        help="Additional price per child beyond double occupancy.",
                                        )
    occupancy_pricing = fields.Selection(
        [('flat', 'Flat Rate'), ('per_pax', 'Per Pax'), ('occupancy_grid', 'Occupancy Grid')],
        string='Occupancy Pricing', required=True, default='flat',
        help="Pricing model:\n- Flat Rate: fixed price regardless of occupancy\n- Per Pax: price varies by number of "
             "guests\n- Occupancy Grid: detailed pricing per occupancy combination.", )
    weekday_mask = fields.Integer(string='Weekday Mask', default=127,
                        help="Bitmask for days of the week (1=Monday, 2=Tuesday, 4=Wednesday, 8=Thursday, 16=Friday,"
                             "32=Saturday, 64=Sunday). Default 127 = all days.",
                                  )
    occupancy_grid_ids = fields.One2many('hospitality.rate.plan.occupancy', 'plan_id',
                                     string='Occupancy Grid',
                                     help="Detailed pricing per adult/children combination for occupancy grid mode.",
                                     )
    notes = fields.Char(string='Notes', help="Internal notes about this rate plan.", )
    audit_reason = fields.Char(string='Audit Reason', store=False,
                               help="Reason for modification. Required when editing locked records.",
                               )

    def _compute_display_name(self):
        """Generate display name from rate code, space type, and date range."""
        for rec in self:
            parts = [rec.rate_code_id.name or 'New', rec.space_type_id.name]
            label = ' - '.join(p for p in parts if p)
            if rec.date_from and rec.date_to:
                label += ' (%s \u2192 %s)' % (
                    rec.date_from.strftime('%b %d'),
                    rec.date_to.strftime('%b %d'),
                )
            rec.display_name = label

    def _is_audit_locked(self):
        """Override this method to implement lock logic. Returns False by default."""
        return False

    @api.model_create_multi
    def create(self, vals_list):
        """Create rate plans with initial audit log entry."""
        records = super().create(vals_list)
        audit_vals = []
        for rec in records:
            after_state = {}
            for f in rec._fields:
                if f in ['create_uid', 'create_date', 'write_uid', 'write_date', 'audit_reason']:
                    continue
                val = rec[f]
                if isinstance(val, models.BaseModel):
                    if rec._fields[f].type in ('one2many', 'many2many'):
                        after_state[f] = val.ids
                    else:
                        after_state[f] = val.id
                else:
                    after_state[f] = val
            audit_vals.append({
                'rate_code_id': rec.rate_code_id.id,
                'model': self._name,
                'record_id': rec.id,
                'before_json': '{}',
                'after_json': json.dumps(after_state, default=str),
                'reason': 'Initial Creation',
            })
        if audit_vals:
            self.env['hospitality.rate.audit'].sudo().create(audit_vals)
        return records

    def write(self, vals):
        """Write with audit logging and immutability enforcement."""
        reason = vals.pop('audit_reason', None)
        is_locked = any(rec._is_audit_locked() for rec in self)
        if is_locked:
            if not self.env.user.has_group('hospitality_rate.group_rate_admin'):
                raise AccessError("You do not have permission to modify an audit-locked rate plan.")
            if not reason:
                raise UserError("You must provide an 'audit_reason' when modifying a locked record.")
        track_fields = [k for k in vals.keys() if k in self._fields]
        before_states = {}
        for rec in self:
            state = {}
            for f in track_fields:
                val = rec[f]
                if isinstance(val, models.BaseModel):
                    state[f] = val.ids if self._fields[f].type in ['one2many', 'many2many'] else val.id
                else:
                    state[f] = val
            before_states[rec.id] = state
        res = super().write(vals)
        audit_vals = []
        for rec in self:
            after_state = {}
            for f in track_fields:
                val = rec[f]
                if isinstance(val, models.BaseModel):
                    after_state[f] = val.ids if self._fields[f].type in ['one2many', 'many2many'] else val.id
                else:
                    after_state[f] = val
            audit_vals.append({
                'rate_code_id': rec.rate_code_id.id,
                'model': self._name,
                'record_id': rec.id,
                'before_json': json.dumps(before_states[rec.id], default=str),
                'after_json': json.dumps(after_state, default=str),
                'reason': reason,
            })
        if audit_vals:
            self.env['hospitality.rate.audit'].sudo().create(audit_vals)
        return res

    @api.constrains('date_from', 'date_to')
    def _check_date_validity(self):
        """Ensure end date is not earlier than start date."""
        for record in self:
            if record.date_from and record.date_to and record.date_to < record.date_from:
                raise ValidationError("End date cannot be earlier than start date.")

    @api.constrains('weekday_mask')
    def _check_weekday_mask(self):
        """Ensure weekday mask is within valid range (1-127)."""
        for record in self:
            if not (1 <= record.weekday_mask <= 127):
                raise ValidationError("Weekday mask must be between 1 and 127.")

    @api.constrains('rate_code_id', 'space_type_id', 'date_from', 'date_to')
    def _check_overlap(self):
        """Prevent overlapping rate plans for the same rate code and space type."""
        for record in self:
            if not (record.rate_code_id and record.space_type_id and record.date_from and record.date_to):
                continue
            domain = [
                ('id', '!=', record.id),
                ('rate_code_id', '=', record.rate_code_id.id),
                ('space_type_id', '=', record.space_type_id.id),
                ('date_from', '<=', record.date_to),
                ('date_to', '>=', record.date_from),
            ]
            if self.search_count(domain):
                raise ValidationError("The date range overlaps with an existing rate plan.")

    @api.constrains('occupancy_pricing', 'occupancy_grid_ids')
    def _check_grid_required(self):
        """Ensure occupancy grid lines exist when using occupancy_grid mode."""
        for record in self:
            if record.occupancy_pricing == 'occupancy_grid' and not record.occupancy_grid_ids:
                raise ValidationError("Occupancy Grid mode requires at least one occupancy grid line.")

    def _price_for_night(self, the_date, adults, children):
        """
        Calculate price for a specific night based on occupancy.

        :param the_date: date of the night
        :param adults: number of adults
        :param children: number of children
        :return: float price or None if weekday not active
        """
        self.ensure_one()
        weekday_bit = the_date.weekday()
        if not (self.weekday_mask & (1 << weekday_bit)):
            return None
        if self.occupancy_pricing == 'flat':
            return self.price_double
        elif self.occupancy_pricing == 'per_pax':
            base = self.price_single if adults == 1 else self.price_double
            extras = max(0, adults - 2) * self.price_extra_adult + children * self.price_extra_child
            return base + extras
        elif self.occupancy_pricing == 'occupancy_grid':
            grid_line = self.occupancy_grid_ids.filtered(lambda l: l.adults == adults and
                                                                   l.children == children)
            if not grid_line:
                raise ValidationError("No occupancy grid price defined.")
            return grid_line[0].price
        return None

    @api.model
    def _upsert_cell(self, rate_code_id, space_type_id, the_date, price):
        """
        Insert or update a single date cell's price.

        Splits existing plans if the date falls within a range.
        """
        if isinstance(the_date, str):
            the_date = fields.Date.from_string(the_date)
        plan = self.search([
            ('rate_code_id', '=', rate_code_id),
            ('space_type_id', '=', space_type_id),
            ('date_from', '<=', the_date),
            ('date_to', '>=', the_date),
        ], limit=1)
        if plan and plan.date_from == the_date and plan.date_to == the_date:
            plan.write({'price_single': price, 'price_double': price})
            return plan
        if plan:
            original_from = plan.date_from
            original_to = plan.date_to
            template = {
                'rate_code_id': plan.rate_code_id.id,
                'space_type_id': plan.space_type_id.id,
                'occupancy_pricing': plan.occupancy_pricing,
                'price_single': plan.price_single,
                'price_double': plan.price_double,
                'price_extra_adult': plan.price_extra_adult,
                'price_extra_child': plan.price_extra_child,
                'currency_id': plan.currency_id.id,
                'weekday_mask': plan.weekday_mask,
                'notes': plan.notes,
            }
            plan.unlink()
            if original_from < the_date:
                self.create({**template, 'date_from': original_from, 'date_to': the_date - timedelta(days=1)})
            middle = self.create(
                {**template, 'date_from': the_date, 'date_to': the_date, 'price_single': price, 'price_double': price})
            if original_to > the_date:
                self.create({**template, 'date_from': the_date + timedelta(days=1), 'date_to': original_to})
            return middle
        return self.create({
            'rate_code_id': rate_code_id,
            'space_type_id': space_type_id,
            'date_from': the_date,
            'date_to': the_date,
            'price_single': price,
            'price_double': price,
            'occupancy_pricing': 'flat',
        })

    @api.model
    def _copy_range(self, rate_code_id, src_from, src_to, dst_from, dst_to):
        """
        Copy prices from a source date range to a destination date range.

        Prices are mapped by offset (cyclic if source range is shorter).
        """
        if isinstance(src_from, str): src_from = fields.Date.from_string(src_from)
        if isinstance(src_to, str): src_to = fields.Date.from_string(src_to)
        if isinstance(dst_from, str): dst_from = fields.Date.from_string(dst_from)
        if isinstance(dst_to, str): dst_to = fields.Date.from_string(dst_to)
        if src_to < src_from or dst_to < dst_from:
            raise ValidationError("Copy range: 'to' date cannot be earlier than 'from' date.")
        src_plans = self.search([
            ('rate_code_id', '=', rate_code_id),
            ('date_from', '<=', src_to),
            ('date_to', '>=', src_from),
        ])
        src_prices = {}
        space_types = src_plans.mapped('space_type_id')
        src_days = (src_to - src_from).days + 1
        for st in space_types:
            type_plans = src_plans.filtered(lambda p: p.space_type_id == st)
            for i in range(src_days):
                d = src_from + timedelta(days=i)
                for p in type_plans:
                    if p.date_from <= d <= p.date_to:
                        src_prices[(st.id, d)] = p.price_double
                        break
        dst_days = (dst_to - dst_from).days + 1
        written = 0
        for i in range(dst_days):
            dst_date = dst_from + timedelta(days=i)
            src_offset = i % src_days if src_days else 0
            src_date = src_from + timedelta(days=src_offset)
            for st in space_types:
                price = src_prices.get((st.id, src_date))
                if price is not None:
                    self._upsert_cell(rate_code_id, st.id, dst_date, price)
                    written += 1
        return written

    @api.model
    def action_upsert_cell(self, rate_code_id, space_type_id, the_date, price):
        """Action wrapper for upsert_cell."""
        plan = self._upsert_cell(rate_code_id, space_type_id, the_date, price)
        return plan.id

    @api.model
    def action_copy_range(self, rate_code_id, src_from, src_to, dst_from, dst_to):
        """Action wrapper for copy_range."""
        return self._copy_range(rate_code_id, src_from, src_to, dst_from, dst_to)
