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

class ResPartner(models.Model):
    """Extends res.partner with hospitality guest profile fields."""
    _inherit = 'res.partner'

    is_guest = fields.Boolean(
        string='Is Guest',
        default=False,
        index=True,
        help='Indicates whether the contact is registered as a hospitality guest.',
    )
    guest_no = fields.Char(
        string='Guest Number',
        readonly=True,
        copy=False,
        index=True,
        help='Unique number assigned to the guest profile.',
    )
    nationality_id = fields.Many2one(
        comodel_name='res.country',
        string='Nationality',
        ondelete='restrict',
        help='Nationality of the guest.',
    )
    birth_date = fields.Date(
        string='Date of Birth',
        help='Date of birth of the guest.',
    )
    gender = fields.Selection(
        selection=[
            ('male',        'Male'),
            ('female',      'Female'),
            ('other',       'Other'),
            ('undisclosed', 'Prefer not to say'),
        ],
        string='Gender',
        help='Gender of the guest.',
    )
    preferred_language_id = fields.Many2one(
        comodel_name='res.lang',
        string='Preferred Language',
        ondelete='restrict',
        help='Preferred language for communicating with the guest.',
    )
    preferred_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Preferred Currency',
        ondelete='restrict',
        help='Preferred currency for displaying guest-related amounts.',
    )
    vip_level = fields.Selection(
        selection=[
            ('none',     'None'),
            ('silver',   'Silver'),
            ('gold',     'Gold'),
            ('platinum', 'Platinum'),
        ],
        string='VIP Level',
        default='none',
        group_expand=True,
        help='VIP level assigned to the guest.',
    )
    dietary_restriction_ids = fields.Many2many(
        comodel_name='hospitality.dietary',
        relation='partner_dietary_rel',
        column1='partner_id',
        column2='dietary_id',
        string='Dietary Restrictions',
        help='Dietary restrictions or requirements of the guest.',
    )
    preference_ids = fields.Many2many(
        comodel_name='hospitality.guest.preference',
        relation='partner_preference_rel',
        column1='partner_id',
        column2='preference_id',
        string='Preferences',
        help='Hospitality preferences specified by the guest.',
    )
    marketing_consent_email = fields.Boolean(
        string='Email Marketing Consent',
        default=False,
        help='Indicates whether the guest has consented to email marketing.',
    )
    marketing_consent_sms = fields.Boolean(
        string='SMS Marketing Consent',
        default=False,
        help='Indicates whether the guest has consented to SMS marketing.',
    )
    gdpr_consent_at = fields.Datetime(
        string='GDPR Consent Timestamp',
        readonly=True,
        help='Date and time when GDPR consent was recorded.',
    )
    gdpr_consent_ip = fields.Char(
        string='GDPR Consent IP',
        readonly=True,
        help='IP address from which GDPR consent was recorded.',
    )
    blacklist = fields.Boolean(
        string='Blacklisted',
        default=False,
        tracking=True,
        help='Indicates whether the guest is currently blacklisted.',
    )
    blacklist_reason = fields.Text(
        string='Blacklist Reason',
        help='Reason why the guest was blacklisted.',
    )
    rtbf_requested_at = fields.Datetime(
        string='RTBF Requested At',
        readonly=True,
        copy=False,
        help='Date and time when the guest requested data erasure.',
    )
    rtbf_requested_by = fields.Many2one(
        comodel_name='res.users',
        string='RTBF Requested By',
        readonly=True,
        copy=False,
        ondelete='set null',
        help='User who recorded the RTBF request.',
    )
    rtbf_anonymized_at = fields.Datetime(
        string='Anonymized At',
        readonly=True,
        copy=False,
        help='Date and time when the guest data was anonymized.',
    )
    id_document_ids = fields.One2many(
        comodel_name='hospitality.guest.id.document',
        inverse_name='partner_id',
        string='Identity Documents',
        help='Identity documents associated with the guest.',
    )
    history_line_ids = fields.One2many(
        comodel_name='hospitality.guest.history.line',
        inverse_name='partner_id',
        string='Stay History',
        help='Historical stays associated with the guest.',
    )
    total_stays = fields.Integer(
        string='Total Stays',
        compute='_compute_history_kpis',
        store=True,
        help='Total number of stays recorded for the guest.',
    )
    total_nights = fields.Integer(
        string='Total Nights',
        compute='_compute_history_kpis',
        store=True,
        help='Total number of nights recorded across the guest stays.',
    )
    total_revenue = fields.Monetary(
        string='Total Revenue',
        currency_field='preferred_currency_id',
        compute='_compute_history_kpis',
        store=True,
        help='Total revenue generated from the guest stays.',
    )
    # ── Card helpers ──────────────────────────────────────────────────
    # Odoo generates an initial-based avatar when a partner has no
    # photograph, but in this build /web/image serves that generated
    # fallback as application/octet-stream, which a browser will not
    # draw - the same defect that breaks the user-menu avatar. The guest
    # kanban therefore draws its own monogram instead of relying on it,
    # and needs to know which case it is in without reading a base64
    # payload per row.
    guest_has_photo = fields.Boolean(
        string='Has Photo',
        compute='_compute_guest_card_fields',
        store=True,
        help='True when the guest has an uploaded photograph, as opposed '
             'to the avatar Odoo generates.',
    )
    guest_initials = fields.Char(
        string='Initials',
        compute='_compute_guest_card_fields',
        store=True,
        help='Up to two initials, shown on the guest card when there is '
             'no photograph.',
    )

    last_stay_date = fields.Date(
        string='Last Stay',
        compute='_compute_history_kpis',
        store=True,
        help='Check-out date of the guest most recent stay.',
    )

    @api.depends('image_1920', 'name')
    def _compute_guest_card_fields(self):
        """Photo presence and initials for the guest kanban card."""
        for partner in self:
            partner.guest_has_photo = bool(partner.image_1920)
            words = [w for w in (partner.name or '').split() if w]
            partner.guest_initials = ''.join(
                w[0].upper() for w in words[:2]
            ) or '?'

    def action_request_rtbf(self):
        """Guest User action: record the RTBF request and post to chatter."""
        self.ensure_one()
        self.write({
            'rtbf_requested_at': fields.Datetime.now(),
            'rtbf_requested_by': self.env.uid,
        })
        self.message_post(
            body=f"RTBF (Right to be Forgotten) requested by {self.env.user.name}.",
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        return True

    def action_open_rtbf_wizard(self):
        """Admin action: open the RTBF confirmation wizard."""
        self.ensure_one()
        wizard = self.env['hospitality.guest.rtbf.wizard'].create({
            'partner_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Execute RTBF — Confirm Anonymisation',
            'res_model': 'hospitality.guest.rtbf.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.depends(
        'history_line_ids',
        'history_line_ids.nights',
        'history_line_ids.revenue',
        'history_line_ids.check_out',
    )
    def _compute_history_kpis(self):
        """Compute historical stays kpis."""
        for partner in self:
            lines = partner.history_line_ids
            partner.total_stays = len(lines)
            partner.total_nights = sum(lines.mapped('nights'))
            partner.total_revenue = sum(lines.mapped('revenue'))
            check_outs = lines.filtered('check_out').mapped('check_out')
            partner.last_stay_date = max(check_outs) if check_outs else False

    @api.model_create_multi
    def create(self, vals_list):
        """Override this method to automatically generate guest number when a new record is created."""
        for vals in vals_list:
            if vals.get('is_guest') and not vals.get('guest_no'):
                vals['guest_no'] = self.env['ir.sequence'].next_by_code(
                    'hospitality.guest.no'
                ) or '/'
        return super().create(vals_list)

    @api.constrains('blacklist', 'blacklist_reason')
    def _check_blacklist_reason(self):
        """Ensure the blacklist reason field is set when a guest is blacklisted."""
        for rec in self:
            if rec.blacklist and not rec.blacklist_reason:
                raise ValidationError(
                    "A reason is mandatory when blacklisting a guest."
                )
