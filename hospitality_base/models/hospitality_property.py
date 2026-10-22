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
import pytz
from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

class HospitalityProperty(models.Model):
    """Manage hospitality properties and their operational settings."""
    _name = 'hospitality.property'
    _description = 'Hospitality Property'
    _order = 'company_id, code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _tz_get(self):
        """Return full pytz timezone selection list."""
        return [(tz, tz) for tz in sorted(pytz.all_timezones)]

    name = fields.Char(
        string='Property Name',
        required=True,
        translate=True,
        tracking=True,
        help='Name of the hospitality property.',
    )
    code = fields.Char(
        string='Code',
        size=16,
        required=True,
        index=True,
        tracking=True,
        help='Short property code, e.g. NYC01.',
    )
    brand_id = fields.Many2one(
        comodel_name='hospitality.brand',
        string='Brand',
        ondelete='restrict',
        tracking=True,
        help='Hospitality brand associated with the property.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self.env.company,
        help='Company that owns or operates the property.',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Legal Entity',
        domain=[('is_company', '=', True)],
        help='Legal entity used for invoicing.',
    )
    property_type = fields.Selection(
        selection=[
            ('hotel', 'Hotel'),
            ('resort', 'Resort'),
            ('vacation_rental', 'Vacation Rental'),
            ('hostel', 'Hostel'),
            ('serviced_apt', 'Serviced Apartment'),
            ('mixed', 'Mixed'),
        ],
        string='Property Type',
        required=True,
        default='hotel',
        help='Type of hospitality property.',
    )
    star_rating = fields.Selection(
        selection=[
            ('1', '1 Star'),
            ('2', '2 Stars'),
            ('3', '3 Stars'),
            ('4', '4 Stars'),
            ('5', '5 Stars'),
        ],
        string='Star Rating',
        help='Official star rating of the property.',
    )
    address_id = fields.Many2one(
        comodel_name='res.partner',
        string='Physical Address',
        help='Physical address of the property.',
    )
    timezone = fields.Selection(
        selection='_tz_get',
        string='Timezone',
        required=True,
        default='UTC',
        help='Timezone used for the property operations and business date.',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        help='Currency used for the property transactions.',
    )
    default_check_in_time = fields.Float(
        string='Default Check-In Time',
        default=14.0,
        help='Hour of day for default check-in (e.g. 14.0 = 2:00 PM).',
    )
    default_check_out_time = fields.Float(
        string='Default Check-Out Time',
        default=12.0,
        help='Hour of day for default check-out (e.g. 12.0 = 12:00 PM).',
    )
    business_date = fields.Date(
        string='Business Date',
        required=True,
        copy=False,
        tracking=True,
        default=fields.Date.today,
        help='Current business date. Advances only during night audit.',
    )
    auto_audit = fields.Boolean(
        string='Auto Night Audit',
        default=False,
        help='Automatically start night audit at 02:00 local time.',
    )
    sequence_reservation_id = fields.Many2one(
        comodel_name='ir.sequence',
        string='Reservation Sequence',
        copy=False,
        help='Sequence used to generate reservation references for the property.',
    )
    sequence_folio_id = fields.Many2one(
        comodel_name='ir.sequence',
        string='Folio Sequence',
        copy=False,
        help='Sequence used to generate folio references for the property.',
    )
    sequence_invoice_id = fields.Many2one(
        comodel_name='ir.sequence',
        string='Invoice Sequence',
        copy=False,
        help='Sequence used to generate invoice references for the property.',
    )
    property_image = fields.Image(
        string='Cover Image',
        max_width=1024,
        max_height=1024,
        help='The single representative shot: the kanban card, and '
             'anything else needing one image, reads this one.',
    )
    image_ids = fields.One2many(
        comodel_name='hospitality.property.image',
        inverse_name='property_id',
        string='Images',
        copy=True,
        help='Gallery for the property - exterior, lobby, rooms, pool, '
             'dining. Ordered by the sequence on each image.',
    )
    image_count = fields.Integer(
        string='Image Count',
        compute='_compute_image_count',
        help='Number of gallery images, excluding the cover.',
    )
    active = fields.Boolean(string='Active', default=True,
                            help='Indicates whether the property is active and available for use.',
    )
    user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='hospitality_property_users_rel',
        column1='property_id',
        column2='user_id',
        string='Assigned Users',
        help='Users assigned to manage or access this property.',
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Sales Journal',
        domain="[('type', '=', 'sale'), ('company_id', '=', company_id)]",
        help='Journal used when folio postings are transferred to accounting.',
    )

    @api.constrains('code', 'company_id')
    def _check_code_unique(self):
        """Ensure the Property code is unique."""
        for property in self:
            if not property.code:
                continue
            duplicate = self.search([
                ('code', '=', property.code),
                ('company_id', '=', property.company_id.id),
                ('id', '!=', property.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "Property code '%s' must be unique per company."
                    % property.code
                )

    @api.constrains('default_check_in_time', 'default_check_out_time')
    def _check_times(self):
        """Check in and check out time should be between 0 and 24 hours."""
        for prop in self:
            if not (0 <= prop.default_check_in_time < 24):
                raise ValidationError(
                    'Check-in time must be between 0 and 24 hours.')
            if not (0 <= prop.default_check_out_time < 24):
                raise ValidationError(
                    'Check-out time must be between 0 and 24 hours.')

    @api.constrains('partner_id')
    def _check_partner_is_company(self):
        """Legal Entity must be a company-type partner"""
        for prop in self:
            if prop.partner_id and not prop.partner_id.is_company:
                raise ValidationError(
                    'Legal Entity must be a company-type partner.')

    @api.depends('image_ids')
    def _compute_image_count(self):
        """How many gallery images the property carries."""
        counts = dict(self.env['hospitality.property.image']._read_group(
            [('property_id', 'in', self.ids)],
            groupby=['property_id'], aggregates=['__count'],
        ))
        for prop in self:
            prop.image_count = counts.get(prop, 0)

    def _compute_display_name(self):
        """Compute the display name of this property."""
        for prop in self:
            prop.display_name = '[%s] %s' % (prop.code, prop.name)

    def _create_property_sequence(self, seq_type, code, company_id):
        """Create and return an ir.sequence for this property.

        :param str seq_type: 'reservation', 'folio', or 'invoice'
        :param str code: property code, e.g. 'NYC01'
        :param int company_id: company ID
        :returns ir.sequence: newly created sequence record
        """
        config = {
            'reservation': {
                'name': 'Reservation / %s' % code,
                'code': 'hospitality.reservation.%s' % code.lower(),
                'prefix': 'RES/%s/%%(year)s/' % code,
                'padding': 5,
            },
            'folio': {
                'name': 'Folio / %s' % code,
                'code': 'hospitality.folio.%s' % code.lower(),
                'prefix': 'FOL/%s/%%(year)s/' % code,
                'padding': 6,
            },
            'invoice': {
                'name': 'Invoice / %s' % code,
                'code': 'hospitality.invoice.%s' % code.lower(),
                'prefix': 'INV/%s/%%(year)s/' % code,
                'padding': 6,
            },
        }
        cfg = config[seq_type]
        return self.env['ir.sequence'].create({
            'name': cfg['name'],
            'code': cfg['code'],
            'prefix': cfg['prefix'],
            'padding': cfg['padding'],
            'company_id': company_id,
            'number_next': 1,
            'number_increment': 1,
        })

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-create the three sequences for each new property
        if not supplied explicitly by the caller.
        """
        for vals in vals_list:
            code = vals.get('code', 'PROP').upper()
            company_id = vals.get('company_id') or self.env.company.id
            if not vals.get('sequence_reservation_id'):
                seq = self._create_property_sequence(
                    'reservation', code, company_id)
                vals['sequence_reservation_id'] = seq.id
            if not vals.get('sequence_folio_id'):
                seq = self._create_property_sequence(
                    'folio', code, company_id)
                vals['sequence_folio_id'] = seq.id
            if not vals.get('sequence_invoice_id'):
                seq = self._create_property_sequence(
                    'invoice', code, company_id)
                vals['sequence_invoice_id'] = seq.id
        return super().create(vals_list)

    def write(self, vals):
        """Only Hospitality Admin can advance the business date."""
        if 'business_date' in vals:
            is_admin = self.env.user.has_group(
                'hospitality_base.group_hospitality_admin'
            )
            if not is_admin:
                raise AccessError(
                    "Only a Hospitality Administrator can change the "
                    "business date. Please run the night audit process."
                )
        return super().write(vals)

    @api.model
    def _cron_business_date_safety(self):
        """Daily safety check: warn if business_date has fallen behind.

        For each active property where business_date < today - 1 day,
        post a chatter message and schedule a warning activity for the
        property manager.
        """
        today = fields.Date.today()
        threshold = today - timedelta(days=1)
        lagging = self.search([
            ('active', '=', True),
            ('business_date', '<', threshold),
        ])
        for prop in lagging:
            lag_days = (today - prop.business_date).days
            message = (
                "⚠️ Business date safety warning: the business date for "
                "%s is %s — %d day(s) behind today (%s). "
                "Please run the night audit to advance it."
                % (prop.display_name, prop.business_date, lag_days, today)
            )
            prop.message_post(
                body=message,
                subject='Business Date Behind — %s' % prop.code,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
            activity_type = self.env.ref(
                'mail.mail_activity_data_warning', raise_if_not_found=False
            ) or self.env['mail.activity.type'].search(
                [('category', '=', 'default')], limit=1
            )
            if activity_type:
                prop.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary='Business date lagging by %d day(s)' % lag_days,
                    note=message,
                    user_id=prop.user_ids[:1].id if prop.user_ids
                    else self.env.ref('base.user_admin').id,
                )
