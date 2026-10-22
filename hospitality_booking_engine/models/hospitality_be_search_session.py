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
import logging
import uuid
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

RECOVERY_WINDOWS = (
    (0, timedelta(hours=1),
     'hospitality_booking_engine.mail_template_be_cart_recovery_1h',
     'abandoned'),
    (1, timedelta(hours=24),
     'hospitality_booking_engine.mail_template_be_cart_recovery_24h',
     'abandoned'),
    (2, timedelta(days=7),
     'hospitality_booking_engine.mail_template_be_cart_recovery_7d',
     'lost'),
)


class HospitalityBeSearchSession(models.Model):
    """Stores a guest's booking engine search and shopping cart session.
    Tracks the visitor's search criteria, selected rate plan and room
    type, guest details, applied promotions, upsells, payment
    transaction, and reservation status. It also supports abandoned
    cart recovery by monitoring session activity and sending automated
    reminder emails to encourage guests to complete their bookings.
    """
    _name = 'hospitality.be.search.session'
    _description = 'Booking Engine Search Session'
    _order = 'last_activity_at desc'

    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        required=True,
        ondelete='cascade',
    )
    visitor_id = fields.Char(string='Visitor ID', index=True)
    search_payload = fields.Json(string='Search Payload')
    selected_rate_code_id = fields.Many2one(
        comodel_name='hospitality.rate.code',
        string='Selected Rate Code',
    )
    selected_space_type_id = fields.Many2one(
        comodel_name='hospitality.space.type',
        string='Selected Room Type',
    )
    arrival = fields.Date(string='Arrival')
    departure = fields.Date(string='Departure')
    adults = fields.Integer(string='Adults')
    children = fields.Integer(string='Children')
    contact_email = fields.Char(string='Contact Email')
    contact_phone = fields.Char(string='Contact Phone')
    started_at = fields.Datetime(string='Started At', default=fields.Datetime.now)
    last_activity_at = fields.Datetime(
        string='Last Activity At',
        default=fields.Datetime.now,
        index=True,
    )
    recovered = fields.Boolean(string='Recovered', default=False)
    recovery_attempts = fields.Integer(string='Recovery Attempts', default=0)
    state = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('abandoned', 'Abandoned'),
            ('recovered', 'Recovered'),
            ('lost', 'Lost'),
        ],
        string='Status',
        default='active',
        required=True,
        index=True,
    )
    access_token = fields.Char(
        string='Access Token',
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: uuid.uuid4().hex,
    )
    promo_code_id = fields.Many2one(
        comodel_name='hospitality.be.promo.code',
        string='Promo Code',
    )
    upsell_ids = fields.Many2many(
        comodel_name='hospitality.be.upsell',
        relation='hospitality_be_search_session_upsell_rel',
        column1='session_id',
        column2='upsell_id',
        string='Upsells',
    )
    guest_name = fields.Char(string='Guest Name')
    guest_nationality_id = fields.Many2one('res.country', string='Nationality')
    guest_notes = fields.Text(string='Special Requests')
    payment_provider_id = fields.Many2one('payment.provider', string='Payment Provider')
    payment_transaction_id = fields.Many2one(
        'payment.transaction', string='Payment Transaction', copy=False
    )
    reservation_id = fields.Many2one(
        'hospitality.reservation', string='Reservation', copy=False, readonly=True
    )

    def _lookup_url(self):
        """Build the public booking lookup URL for this search session.
        Returns:
            str: Absolute URL containing the session access token that allows
            the guest to reopen and continue the booking process.
        """
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', ''
        )
        return f"{base_url}/booking/lookup?token={self.access_token}"

    def _send_recovery_email(self, template_xmlid):
        """Send an abandoned-cart recovery email using the specified template.
        Args:
            template_xmlid (str): XML ID of the mail template to use.
        Returns:
            bool: True if the email was successfully queued for sending,
            otherwise False (for example, when the template or contact
            email is unavailable).
        """
        self.ensure_one()
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template or not self.contact_email:
            return False
        template.send_mail(
            self.id,
            force_send=False,
            email_values={'email_to': self.contact_email},
        )
        return True

    @api.model
    def cron_abandoned_cart_recovery(self):
        """Cron job that processes abandoned booking sessions.
        Checks inactive booking sessions against the configured recovery
        windows, sends the appropriate reminder email, increments the
        recovery attempt count, and updates the session state to
        'abandoned' or 'lost' as required.
        """
        now = fields.Datetime.now()
        sessions = self.search([
            ('state', 'not in', ('recovered', 'lost')),
            ('contact_email', '!=', False),
            ('last_activity_at', '!=', False),
        ])
        for attempts_sent, min_idle, template_xmlid, next_state in RECOVERY_WINDOWS:
            due = sessions.filtered(
                lambda s, attempts_sent=attempts_sent, min_idle=min_idle: (
                    s.recovery_attempts == attempts_sent
                    and s.last_activity_at <= now - min_idle
                )
            )
            for session in due:
                if session._send_recovery_email(template_xmlid):
                    session.write({
                        'recovery_attempts': session.recovery_attempts + 1,
                        'state': next_state,
                    })
                else:
                    _logger.info(
                        "Skipped recovery email for search session %s: "
                        "missing template or contact email.",
                        session.id,
                    )

    @api.model
    def _recover_for_confirmed_reservation(self, property_id, contact_email,
                                            arrival, departure):
        """Mark matching abandoned booking sessions as recovered.
        Searches for booking sessions matching the given property, guest
        email, and stay dates, then updates their status once a reservation
        has been successfully confirmed.
        Args:
            property_id (int): Property identifier.
            contact_email (str): Guest email address.
            arrival (date): Arrival date.
            departure (date): Departure date.
        Returns:
            recordset: Matching booking search sessions that were updated.
        """
        sessions = self.search([
            ('property_id', '=', property_id),
            ('contact_email', '=', contact_email),
            ('arrival', '=', arrival),
            ('departure', '=', departure),
            ('state', 'not in', ('recovered', 'lost')),
        ])
        if sessions:
            sessions.write({'recovered': True, 'state': 'recovered'})
        return sessions

    def _get_rate_quote(self):
        """Calls the real RATE-06 canonical pricing API:

            rate_code._get_rate(property_id, space_type_id, rate_code_id,
                                 arrival, departure, occupancy)

        (all positional; arrival/departure must be date objects, not
        strings; occupancy is a dict, not separate kwargs).

        Returns {'total': float, 'currency_id': int} on success, or
        None if unpriceable (missing rate plan for any night, or a
        restriction violation for the stay)."""
        self.ensure_one()
        if not (self.selected_rate_code_id and self.selected_space_type_id
                and self.arrival and self.departure):
            return None
        try:
            arrival = fields.Date.to_date(self.arrival)
            departure = fields.Date.to_date(self.departure)
            raw = self.selected_rate_code_id._get_rate(
                self.property_id.id,
                self.selected_space_type_id.id,
                self.selected_rate_code_id.id,
                arrival,
                departure,
                {'adults': self.adults or 1, 'children': self.children or 0},
            )
        except Exception:
            _logger.exception("Rate quote failed for search session %s", self.id)
            return None

        if not raw or raw.get('restrictions'):
            return None
        nightly = raw.get('nightly') or []
        if not nightly or any(price is None for _date, price in nightly):
            return None
        total = sum(price for _date, price in nightly)
        return {'total': total, 'currency_id': raw.get('currency_id')}

    def _get_cart_lines(self):
        """Build the booking cart line data for display.
        Returns:
            list: A list containing the selected accommodation details and
            calculated pricing, or an empty list if pricing cannot be
            determined.
        """
        self.ensure_one()
        rate_info = self._get_rate_quote()
        if not rate_info:
            return []
        total = rate_info.get('total')
        return [{
            'id': self.id,
            'space_type_name': self.selected_space_type_id.name,
            'arrival': self.arrival,
            'departure': self.departure,
            'adults': self.adults,
            'price_display': f"{total:.2f}" if total is not None else '',
        }]

    def _cart_totals(self):
        """NOTE: tax computation is not implemented (taxes_display is
        always '0.00') — out of scope for BE-05 as specified; revisit
        if a later task requires real tax lines."""
        self.ensure_one()
        rate_info = self._get_rate_quote() or {}
        subtotal = rate_info.get('total') or 0.0
        currency_id = rate_info.get('currency_id') or (
            self.property_id.currency_id.id
            if 'currency_id' in self.property_id._fields else False
        )
        upsell_total = sum(u.price for u in self.upsell_ids if 'price' in u._fields)

        discount = 0.0
        if self.promo_code_id:
            if self.promo_code_id.discount_pct:
                discount = (subtotal + upsell_total) * (self.promo_code_id.discount_pct / 100.0)
            elif self.promo_code_id.discount_fixed:
                discount = min(self.promo_code_id.discount_fixed, subtotal + upsell_total)

        total = max(subtotal + upsell_total - discount, 0.0)
        return {
            'subtotal': subtotal,
            'total': total,
            'currency_id': currency_id,
            'subtotal_display': f"{subtotal + upsell_total:.2f}",
            'taxes_display': "0.00",
            'total_display': f"{total:.2f}",
        }

    def _apply_promo_code(self, code):
        """"Apply a valid promo code to the booking session.
        Args:
            code (str): Promo code entered by the guest.
        Returns:
            bool: True if a matching active promo code was found and
            applied, otherwise False.
        """
        self.ensure_one()
        domain = [('code', '=', code)]
        if 'active' in self.env['hospitality.be.promo.code']._fields:
            domain.append(('active', '=', True))
        promo = self.env['hospitality.be.promo.code'].sudo().search(domain, limit=1)
        if promo:
            self.promo_code_id = promo.id
        return bool(promo)

    def _add_upsell(self, upsell_id):
        """Add an upsell product or service to the booking session.
        Args:
            upsell_id (int): Identifier of the upsell record to add.
        """
        self.ensure_one()
        self.upsell_ids = [(4, upsell_id)]

    def _get_or_create_partner(self):
        """Get or create a res.partner for the guest.

        Works for any visitor — existing or new. If the email already
        exists in the system, reuses that partner. Otherwise creates a
        brand-new partner record so the reservation/folio always have
        a valid partner_id (which is NOT NULL on hospitality.folio).
        """
        self.ensure_one()
        Partner = self.env['res.partner'].sudo()

        if self.contact_email:
            partner = Partner.search([('email', '=', self.contact_email)], limit=1)
            if partner:
                return partner

        partner_name = self.guest_name or self.contact_email or 'Booking Engine Guest'
        partner_vals = {
            'name': partner_name,
            'email': self.contact_email or False,
        }
        if 'phone' in Partner._fields:
            partner_vals['phone'] = self.contact_phone or False
        if 'country_id' in Partner._fields and self.guest_nationality_id:
            partner_vals['country_id'] = self.guest_nationality_id.id

        partner = Partner.create(partner_vals)
        _logger.info(
            "Created new partner id=%s name=%r for booking engine guest",
            partner.id, partner.name,
        )
        return partner

    def _finalize_booking(self):
        """Create the confirmed reservation + folio from this cart.

        Every field is checked against the target model's _fields
        before being included in the create() call, so this method
        works regardless of which optional fields the real
        hospitality.reservation / hospitality.folio models define.

        The partner is always resolved via _get_or_create_partner()
        which creates a new res.partner for anonymous visitors — this
        satisfies the NOT NULL constraint on hospitality.folio.partner_id.
        """
        self.ensure_one()
        partner = self._get_or_create_partner()

        Reservation = self.env['hospitality.reservation'].sudo()
        Folio = self.env['hospitality.folio'].sudo()

        reservation_vals = {}

        core_fields = {
            'partner_id': partner.id,
            'arrival': self.arrival,
            'departure': self.departure,
            'adults': self.adults or 1,
            'children': self.children or 0,
        }
        for field, value in core_fields.items():
            if field in Reservation._fields:
                reservation_vals[field] = value

        if 'property_id' in Reservation._fields:
            reservation_vals['property_id'] = self.property_id.id

        if 'space_type_id' in Reservation._fields and self.selected_space_type_id:
            reservation_vals['space_type_id'] = self.selected_space_type_id.id
        if 'rate_code_id' in Reservation._fields and self.selected_rate_code_id:
            reservation_vals['rate_code_id'] = self.selected_rate_code_id.id

        if 'state' in Reservation._fields:
            state_field = Reservation._fields['state']
            valid_states = [s[0] for s in state_field.selection] if hasattr(state_field, 'selection') else []
            if 'confirmed' in valid_states:
                reservation_vals['state'] = 'confirmed'
            elif 'draft' in valid_states:
                reservation_vals['state'] = 'draft'

        optional_ref_fields = {
            'created_via': 'booking_engine',
            'channel_id': False,
            'external_id': False,
        }
        for field, value in optional_ref_fields.items():
            if field in Reservation._fields:
                reservation_vals[field] = value

        if 'source_code_id' in Reservation._fields:
            if 'hospitality.source.code' in self.env:
                source = self.env['hospitality.source.code'].sudo().search(
                    [('code', '=', 'DIRECT')], limit=1
                )
                if source:
                    reservation_vals['source_code_id'] = source.id

        if 'market_segment_id' in Reservation._fields:
            if 'hospitality.market.segment' in self.env:
                segment = self.env['hospitality.market.segment'].sudo().search(
                    [('code', '=', 'LEISURE')], limit=1
                )
                if segment:
                    reservation_vals['market_segment_id'] = segment.id

        _logger.info(
            "FINALIZE: creating reservation with vals keys=%s",
            list(reservation_vals.keys()),
        )
        reservation = Reservation.create(reservation_vals)
        _logger.info(
            "FINALIZE: reservation created id=%s name=%s",
            reservation.id,
            getattr(reservation, 'name', 'N/A'),
        )

        folio = False

        if hasattr(reservation, 'action_create_folio'):
            try:
                with self.env.cr.savepoint():
                    folio = reservation.action_create_folio()
                _logger.info(
                    "FINALIZE: folio created via action_create_folio id=%s",
                    folio.id if folio else None,
                )
            except Exception:
                _logger.exception(
                    "FINALIZE: action_create_folio() failed, "
                    "falling back to direct create"
                )
                folio = False

        if not folio:
            folio_vals = {
                'partner_id': partner.id,
                'reservation_id': reservation.id,
            }
            if 'property_id' in Folio._fields:
                folio_vals['property_id'] = self.property_id.id
            if 'currency_id' in Folio._fields and self.property_id.currency_id:
                folio_vals['currency_id'] = self.property_id.currency_id.id

            _logger.info(
                "FINALIZE: creating folio directly with vals keys=%s",
                list(folio_vals.keys()),
            )
            folio = Folio.create(folio_vals)

        if folio and 'partner_id' in folio._fields and not folio.partner_id:
            folio.write({'partner_id': partner.id})
            _logger.info(
                "FINALIZE: patched folio %s with partner_id=%s",
                folio.id, partner.id,
            )

        totals = self._cart_totals()

        deposit_code = self.env.ref(
            'hospitality_folio.tc_deposit_in',
            raise_if_not_found=False,
        )
        if folio and deposit_code:
            folio._post_payment(
                transaction_code_id=deposit_code,
                amount=totals.get('total') or 0.0,
                payment_ref='BE %s' % (
                        self.payment_transaction_id.reference or self.access_token
                ),
            )
        else:
            _logger.error(
                "FINALIZE: deposit NOT posted for reservation %s "
                "(folio=%s, deposit_code=%s) — guest paid but the folio "
                "shows full balance due.",
                reservation.id,
                bool(folio),
                bool(deposit_code),
            )
        if self.promo_code_id and hasattr(self.promo_code_id, '_consume'):
            try:
                with self.env.cr.savepoint():
                    self.promo_code_id._consume()
            except Exception:
                _logger.exception("promo_code._consume() failed")

        self.write({
            'reservation_id': reservation.id,
            'recovered': True,
            'state': 'recovered',
        })

        _logger.info(
            "FINALIZE: booking finalized — reservation=%s folio=%s "
            "partner=%s session=%s",
            reservation.id,
            folio.id if folio else None,
            partner.id,
            self.id,
        )
        return reservation