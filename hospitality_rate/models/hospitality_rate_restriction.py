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

class HospitalityRateRestriction(models.Model):
    """
    Rate Restriction defining booking limitations for rate codes.

    Restrictions include minimum/maximum stay, closed to arrival/departure,
    complete closure, no-show charges, and weekday-specific rules.
    Can apply to all space types or specific ones.
    """
    _name = 'hospitality.rate.restriction'
    _description = 'Hospitality Rate Restriction'
    _order = 'rate_code_id, date_from'

    name = fields.Char(string='Name', compute='_compute_name', store=True, readonly=True,
                       help="Auto-generated name combining rate code, room type, and date range.",
                       )
    rate_code_id = fields.Many2one('hospitality.rate.code', string='Rate Code', required=True,
                           ondelete='cascade',index=True,
                           help="Rate code this restriction applies to. Deleting the rate removes its restrictions.",
                           )
    space_type_id = fields.Many2one('hospitality.space.type', string='Room Type', ondelete='restrict',
                                    help="Room type this restriction applies to. Leave empty for all room types.",
                                    )
    property_id = fields.Many2one('hospitality.property', string='Property',
                                  related='rate_code_id.property_id',
                                  store=True, index=True, readonly=True,
                                  help="Property inherited from the rate code.",
                                  )
    date_from = fields.Date(string='Date From', required=True, index=True,
                            help="Start date of the restriction validity period.",)
    date_to = fields.Date(string='Date To', required=True, index=True,
                          help="End date of the restriction validity period.",
                          )
    min_stay = fields.Integer(string='Min Stay (nights)', default=0,
                              help="Minimum number of nights required. 0 = no minimum restriction.",
                              )
    max_stay = fields.Integer(string='Max Stay (nights)', default=0,
                              help="Maximum number of nights allowed. 0 = no maximum restriction.",
                              )
    cta = fields.Boolean(string='Closed to Arrival', default=False,
                         help="Check to prevent new arrivals on these dates.",
                         )
    ctd = fields.Boolean(string='Closed to Departure', default=False,
                         help="Check to prevent departures on these dates.",
                         )
    closed = fields.Boolean(string='Closed', default=False,
                            help="Check to completely close the rate/room type on these dates.",
                            )
    no_show_charge_pct = fields.Float(string='No-Show Charge %', default=100.0,
                                      help="Percentage of total stay to charge in case of no-show (0-100%).",
                                      )
    notes = fields.Char(string='Notes',help="Internal notes about this restriction.",)
    active = fields.Boolean(string='Active', default=True,help="Uncheck to archive this restriction.",)
    weekday_mask = fields.Integer(
        string='Weekday Mask',
        default=127,
        help='Bitmask for weekdays (Mon=0 ... Sun=6)'
    )
    audit_reason = fields.Char(string='Audit Reason', store=False,
                               help="Reason for modification. Required when editing locked records.",
                               )

    @api.constrains('weekday_mask')
    def _check_weekday_mask(self):
        """Generate display name from rate code, space type, and date range."""
        for rec in self:
            if not (1 <= rec.weekday_mask <= 127):
                raise ValidationError(
                    "Weekday mask must be between 1 and 127."
                )

    @api.depends('rate_code_id', 'space_type_id', 'date_from', 'date_to')
    def _compute_name(self):
        """Ensure end date is not earlier than start date."""
        for rec in self:
            rate = rec.rate_code_id.display_name or ''
            space = rec.space_type_id.display_name or 'All Types'
            df = rec.date_from or ''
            dt = rec.date_to or ''
            rec.name = '%s / %s / %s – %s' % (rate, space, df, dt)

    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):
        """UI feedback for invalid date ranges."""
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValidationError("End date cannot be earlier than start date.")

    @api.onchange('min_stay', 'max_stay')
    def _onchange_stay_values(self):
        """UI feedback for invalid stay values."""
        if self.min_stay < 0 or self.max_stay < 0:
            raise ValidationError("Stay limits cannot be negative.")
        if 0 < self.max_stay < self.min_stay:
            raise ValidationError("Maximum stay cannot be less than minimum stay.")

    @api.onchange('no_show_charge_pct')
    def _onchange_no_show_charge_pct(self):
        """UI feedback for invalid no-show percentage."""
        if self.no_show_charge_pct < 0 or self.no_show_charge_pct > 100:
            raise ValidationError("No-show charge percentage must be between 0 and 100.")

    @api.constrains('date_from', 'date_to')
    def _check_date_validity(self):
        """Ensure end date is not earlier than start date."""
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(
                    "Restriction '%s': End date cannot be earlier than start date." % rec.display_name)

    @api.constrains('min_stay', 'max_stay')
    def _check_stay_values(self):
        """Ensure stay limits are valid (non-negative, max >= min)."""
        for rec in self:
            if rec.min_stay < 0 or rec.max_stay < 0:
                raise ValidationError("Restriction '%s': Stay limits cannot be negative." % rec.display_name)
            if 0 < rec.max_stay < rec.min_stay:
                raise ValidationError(
                    "Restriction '%s': Maximum stay cannot be less than minimum stay." % rec.display_name)

    @api.constrains('no_show_charge_pct')
    def _check_no_show_charge_pct(self):
        """Ensure no-show charge percentage is between 0 and 100."""
        for rec in self:
            if rec.no_show_charge_pct < 0 or rec.no_show_charge_pct > 100:
                raise ValidationError(
                    "Restriction '%s': No-show charge percentage must be between 0 and 100." % rec.display_name)

    def _is_audit_locked(self):
        """Override to implement lock logic. Returns False by default."""
        return False

    @api.model_create_multi
    def create(self, vals_list):
        """Create restrictions with initial audit log entry."""
        records = super().create(vals_list)
        audit_vals = []
        for rec in records:
            after_state = {}
            for f in rec._fields:
                if f in ['create_uid', 'create_date', 'write_uid', 'write_date', 'audit_reason']:
                    continue
                val = rec[f]
                after_state[f] = val.id if isinstance(val, models.BaseModel) else val
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
                raise AccessError("You do not have permission to modify an audit-locked restriction.")
            if not reason:
                raise UserError("You must provide an 'audit_reason' when modifying a locked record.")
        track_fields = [k for k in vals.keys() if k in self._fields]
        before_states = {}
        for rec in self:
            state = {}
            for f in track_fields:
                val = rec[f]
                state[f] = val.id if isinstance(val, models.BaseModel) else val
            before_states[rec.id] = state
        res = super().write(vals)
        audit_vals = []
        for rec in self:
            after_state = {}
            for f in track_fields:
                val = rec[f]
                after_state[f] = val.id if isinstance(val, models.BaseModel) else val
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

    @api.model
    def _evaluate(self, rate_code_id, space_type_id, arrival, departure):
        """
        Evaluate all restrictions for a given booking.

        :param rate_code_id: int, rate code ID
        :param space_type_id: int, space type ID
        :param arrival: date, inclusive arrival
        :param departure: date, exclusive departure
        :return: list of violation code strings
        """
        violations = []
        domain = [
            ('rate_code_id', '=', rate_code_id),
            ('date_from', '<=', departure),
            ('date_to', '>=', arrival),
            '|',
            ('space_type_id', '=', False),
            ('space_type_id', '=', space_type_id),
        ]
        restrictions = self.search(domain)
        if not restrictions:
            return violations
        stay_nights = (departure - arrival).days
        for restriction in restrictions:
            if restriction.closed:
                if 'closed' not in violations: violations.append('closed')
                return violations
            if restriction.cta and restriction.date_from <= arrival <= restriction.date_to:
                if 'cta' not in violations: violations.append('cta')
            if restriction.ctd and restriction.date_from <= departure <= restriction.date_to:
                if 'ctd' not in violations: violations.append('ctd')
            if restriction.min_stay > 0 and stay_nights < restriction.min_stay:
                if 'min_stay' not in violations: violations.append('min_stay')
            if restriction.max_stay > 0 and stay_nights > restriction.max_stay:
                if 'max_stay' not in violations: violations.append('max_stay')
        return violations

    @api.model
    def action_upsert(self, rate_code_id, space_type_id, date_from, date_to, **flags):
        """
        Insert or update a restriction, automatically splitting/truncating overlaps.

        :param rate_code_id: int, rate code ID
        :param space_type_id: int or False, space type ID
        :param date_from: date, start date
        :param date_to: date, end date
        :param flags: restriction flags (closed, cta, ctd, min_stay, max_stay, no_show_charge_pct)
        :return: ID of created restriction
        """
        if isinstance(date_from, str): date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str): date_to = fields.Date.from_string(date_to)
        domain = [
            ('rate_code_id', '=', rate_code_id),
            ('space_type_id', '=', space_type_id or False),
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
        ]
        overlaps = self.search(domain)
        template_fields = ['rate_code_id', 'space_type_id', 'closed', 'cta', 'ctd', 'min_stay', 'max_stay',
                           'no_show_charge_pct', 'notes']
        for rec in overlaps:
            rec_from = rec.date_from
            rec_to = rec.date_to
            if rec_from >= date_from and rec_to <= date_to:
                rec.unlink()
            elif rec_from < date_from and rec_to > date_to:
                rec_vals = {f: rec[f].id if isinstance(rec[f], models.BaseModel) else rec[f] for f in template_fields}
                rec.unlink()
                self.create({**rec_vals, 'date_from': rec_from, 'date_to': date_from - timedelta(days=1)})
                self.create({**rec_vals, 'date_from': date_to + timedelta(days=1), 'date_to': rec_to})
            elif rec_from < date_from and rec_to >= date_from:
                rec.write({'date_to': date_from - timedelta(days=1)})
            elif rec_from <= date_to and rec_to > date_to:
                rec.write({'date_from': date_to + timedelta(days=1)})
        new_rec = self.create({
            'rate_code_id': rate_code_id,
            'space_type_id': space_type_id or False,
            'date_from': date_from,
            'date_to': date_to,
            'closed': flags.get('closed', False),
            'cta': flags.get('cta', False),
            'ctd': flags.get('ctd', False),
            'min_stay': flags.get('min_stay', 0),
            'max_stay': flags.get('max_stay', 0),
            'no_show_charge_pct': flags.get('no_show_charge_pct', 100.0),
        })
        return new_rec.id
