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
import traceback
import uuid as uuid_lib
from datetime import timedelta

from odoo import fields, http
from odoo.tools import _, format_date
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

CART_SESSION_KEY = 'be_cart_session_id'
VISITOR_SESSION_KEY = 'be_visitor_uuid'


class BookingEngineController(http.Controller):
    """Public website controller for the Hospitality Booking Engine.
    Provides the complete guest booking workflow, including property
    search, room availability, cart management, promo codes, upsells,
    guest checkout, payment processing, reservation confirmation, and
    reservation lookup. It also manages visitor sessions, booking
    engine search sessions, and integrates with the hospitality,
    payment, and reservation models to complete online bookings.
    """

    def _get_property(self, property_id=None):
        """Return the property for the current booking flow.
        If a valid property_id is provided, that property is returned.
        Otherwise, the first available hospitality property is used as
        the default.
        """
        Property = request.env['hospitality.property'].sudo()
        if property_id:
            prop = Property.browse(int(property_id))
            if prop.exists():
                return prop
        return Property.search([], limit=1)

    def _get_be_config(self, property_rec):
        """Return the booking engine configuration for a property."""
        return request.env['hospitality.be.config'].sudo().search(
            [('property_id', '=', property_rec.id)], limit=1
        )

    # ------------------------------------------------------------------
    #  Presentation helpers
    # ------------------------------------------------------------------
    def _be_flag(self, be_config, field_name, default=True):
        """Read a display toggle off the booking engine configuration.

        A property that has no hospitality.be.config record yet reads as
        an empty recordset, and every Boolean on an empty recordset is
        False - which would silently switch photographs and amenities
        OFF for exactly the properties nobody has configured yet. Absent
        configuration falls back to the field's own default instead.
        """
        if not be_config:
            return default
        return bool(be_config[field_name])

    def _be_format_date(self, value):
        """Render a date the way the visitor's language writes dates.

        Values arrive here either as a date from the ORM or as the raw
        'YYYY-MM-DD' string a date input posted, so both are accepted.
        """
        if not value:
            return ''
        try:
            if isinstance(value, str):
                value = fields.Date.from_string(value)
            return format_date(request.env, value)
        except Exception:
            return str(value)

    def _be_currency_symbol(self, property_rec):
        """Symbol for the property's currency, or '' when unset.

        Prices are formatted as bare decimals all through this flow; the
        templates put this in front of them so a guest is quoted a
        currency rather than a naked number.
        """
        currency = property_rec.currency_id if property_rec else None
        return (currency and currency.symbol) or ''

    def _be_is_publishable(self, property_rec):
        """True when a property has deliberately been put up for public
        sale - that is, somebody configured a booking engine for it.

        Guards each of the public image routes below; see the long note
        on be_space_type_photo for why images are streamed under sudo
        rather than by widening the operational models' ACLs.
        """
        if not property_rec:
            return False
        return bool(request.env['hospitality.be.config'].sudo().search_count(
            [('property_id', '=', property_rec.id)], limit=1
        ))

    def _be_image_response(self, record, field_name, width=0, height=0):
        """Stream one image field publicly, or Odoo's own placeholder.

        Callers pass a falsy record when their own publishability checks
        fail, so a rejected request is indistinguishable from a record
        that simply has no picture - which is how /web/image behaves too.
        """
        if record and field_name and record[field_name]:
            stream = request.env['ir.binary']._get_image_stream_from(
                record, field_name,
                width=int(width or 0), height=int(height or 0),
            )
        else:
            placeholder = request.env.ref('web.image_placeholder').sudo()
            stream = request.env['ir.binary']._get_image_stream_from(
                placeholder, 'raw',
                width=int(width or 0), height=int(height or 0),
            )
        stream.public = True
        return stream.get_response()

    def _be_space_type_photo_urls(self, space_type, limit=5):
        """Public photo URLs for a room type, lead image first.

        The cover image comes first when there is one, then the type's
        gallery. The fallback matters: a room type very commonly has
        several gallery shots and an empty cover, and the booking engine
        showed no photograph at all in that case.
        """
        urls = []
        if not space_type:
            return urls
        if space_type.image:
            urls.append('/booking/space-type/%s/photo' % space_type.id)
        for image in space_type.image_ids[:limit]:
            urls.append(
                '/booking/space-type/%s/gallery/%s' % (space_type.id, image.id)
            )
        return urls[:limit]

    def _be_space_type_meta(self, space_type):
        """(FontAwesome icon name, label) pairs describing a room type.

        Selection labels come from fields_get so they arrive translated
        rather than as raw database keys.
        """
        meta = []
        if not space_type:
            return meta
        descriptions = space_type.fields_get(['bed_config', 'category'])
        if space_type.max_occupancy:
            meta.append(('user', _('Sleeps %s') % space_type.max_occupancy))
        if space_type.bed_config:
            labels = dict(descriptions['bed_config']['selection'])
            meta.append(('bed', labels.get(space_type.bed_config,
                                           space_type.bed_config)))
        if space_type.size_sqm:
            meta.append(('arrows-alt', _('%s m²') % int(space_type.size_sqm)))
        if space_type.category:
            labels = dict(descriptions['category']['selection'])
            meta.append(('home', labels.get(space_type.category,
                                            space_type.category)))
        return meta

    def _be_amenity_names(self, space_type, limit=None):
        """Amenity labels for a room type, optionally capped."""
        if not space_type:
            return []
        names = [amenity.display_name for amenity in space_type.amenity_ids]
        return names[:limit] if limit else names

    def _be_checkout_summary(self, property_rec, cart):
        """Order-summary values for the checkout page.

        The checkout page carries its own running total, so it needs the
        same figures the cart page renders. It is rendered from three
        places - the normal GET and the two payment-failure paths - and
        a missing key here is a QWeb error halfway down the page, not a
        blank panel, so the failure paths get the full set too.
        """
        values = {
            'currency_symbol': self._be_currency_symbol(property_rec),
            'cart_lines': [],
            'subtotal_display': '',
            'taxes_display': '',
            'total_display': '',
        }
        if not cart or not cart.exists():
            return values
        try:
            totals = cart._cart_totals()
            values.update({
                'cart_lines': cart._get_cart_lines(),
                'subtotal_display': totals.get('subtotal_display') or '',
                'taxes_display': totals.get('taxes_display') or '',
                'total_display': totals.get('total_display') or '',
            })
        except Exception:
            # A summary panel is not worth losing the checkout page over,
            # least of all on a page already reporting a payment failure.
            _logger.exception("Could not build the checkout order summary")
        return values

    def _be_hero_source(self, property_rec, be_config=None):
        """(record, field name) holding a property's hero photograph.

        Falls back from the configured hero image, to the property's own
        cover photo, to the first picture in its gallery, so the search
        page has something to show before anyone uploads a dedicated
        hero. Returns (None, None) when the property has no images.
        """
        if not property_rec:
            return None, None
        if be_config is None:
            be_config = self._get_be_config(property_rec)
        if be_config and be_config.hero_image:
            return be_config, 'hero_image'
        if property_rec.property_image:
            return property_rec, 'property_image'
        gallery = property_rec.image_ids[:1]
        if gallery:
            return gallery, 'image_1920'
        return None, None

    def _be_hero_url(self, property_rec, be_config=None):
        """Public URL of the search page hero image, or False."""
        if not self._be_is_publishable(property_rec):
            return False
        record, field_name = self._be_hero_source(property_rec, be_config)
        if not record:
            return False
        return '/booking/property/%s/hero' % property_rec.id

    def _get_cart(self, property_rec, create=True):
        """Fetch (or create) the hospitality.be.search.session backing
        the current visitor's cart."""
        Session = request.env['hospitality.be.search.session'].sudo()
        session_id = request.session.get(CART_SESSION_KEY)
        cart = Session.browse(session_id) if session_id else Session.browse()
        if not cart.exists():
            if not create:
                return Session.browse()
            visitor_id = request.session.get(VISITOR_SESSION_KEY)
            if not visitor_id:
                visitor_id = uuid_lib.uuid4().hex
                request.session[VISITOR_SESSION_KEY] = visitor_id
            cart = Session.create({
                'property_id': property_rec.id,
                'visitor_id': visitor_id,
            })
            request.session[CART_SESSION_KEY] = cart.id
        else:
            cart.write({'last_activity_at': fields.Datetime.now()})
        return cart

    def _payment_providers(self, property_rec):
        """Return payment providers available for the checkout page.

        Uses a multi-strategy approach to be compatible across Odoo
        versions (17, 18, 19) where the ``state`` selection values and
        website-aware filtering on ``payment.provider`` may differ.
        """
        Provider = request.env['payment.provider'].sudo()

        if hasattr(Provider, '_get_compatible_providers'):
            try:
                currency_id = False
                if 'currency_id' in property_rec._fields and property_rec.currency_id:
                    currency_id = property_rec.currency_id.id
                company_id = False
                if 'company_id' in property_rec._fields and property_rec.company_id:
                    company_id = property_rec.company_id.id
                partner_id = False
                if request.env.user and request.env.user.partner_id:
                    partner_id = request.env.user.partner_id.id
                providers = Provider._get_compatible_providers(
                    company_id=company_id,
                    partner_id=partner_id,
                    amount=0.0,
                    currency_id=currency_id,
                    is_validation=False,
                )
                if providers:
                    _logger.info(
                        "_get_compatible_providers returned: %s",
                        providers.ids,
                    )
                    return providers
            except Exception:
                _logger.exception("_get_compatible_providers() failed")

        try:
            providers = Provider.search([('state', 'not in', ('disabled',))])
            if providers:
                _logger.info(
                    "Strategy 2 (state != disabled) matched: %s",
                    providers.ids,
                )
                return providers
        except Exception:
            _logger.exception("Strategy 2 search failed")

        try:
            if 'active' in Provider._fields:
                providers = Provider.search([('active', '=', True)])
                if providers:
                    _logger.info(
                        "Strategy 3 (active=True) matched: %s",
                        providers.ids,
                    )
                    return providers
        except Exception:
            _logger.exception("Strategy 3 search failed")

        try:
            _logger.warning(
                "All payment-provider search strategies returned empty. "
                "Returning all providers as last resort."
            )
            return Provider.search([])
        except Exception:
            _logger.exception("Strategy 4 search failed")
            return Provider.browse()

    def _get_payment_method_for_provider(self, provider):
        """Return a suitable payment.method record for the given provider.

        In Odoo 19, ``payment.transaction.payment_method_id`` is
        mandatory.  Each ``payment.provider`` exposes its supported
        payment methods via ``payment_method_ids`` (or
        ``available_payment_method_ids`` in some versions).  We pick
        the first one; if none are linked we fall back to searching
        the ``payment.method`` table directly.
        """
        for field_name in ('payment_method_ids', 'available_payment_method_ids'):
            if field_name in provider._fields:
                methods = provider[field_name]
                if methods:
                    _logger.info(
                        "Found payment method via %s: %s (id=%s)",
                        field_name, methods[0].name, methods[0].id,
                    )
                    return methods[0]

        PaymentMethod = request.env['payment.method'].sudo()
        if 'provider_ids' in PaymentMethod._fields:
            method = PaymentMethod.search([
                ('provider_ids', 'in', [provider.id]),
            ], limit=1)
            if method:
                _logger.info(
                    "Found payment method via reverse search: %s (id=%s)",
                    method.name, method.id,
                )
                return method

        method = PaymentMethod.search([], limit=1)
        if method:
            _logger.warning(
                "Using fallback payment.method: %s (id=%s)",
                method.name, method.id,
            )
        return method

    def _get_or_create_partner_for_cart(self, cart):
        """Get or create a res.partner for the cart's guest.

        Handles the case where the custom model may or may not have
        its own _get_or_create_partner method.
        """
        if hasattr(cart, '_get_or_create_partner'):
            try:
                with request.env.cr.savepoint():
                    return cart._get_or_create_partner()
            except Exception:
                _logger.exception("cart._get_or_create_partner() failed")

        Partner = request.env['res.partner'].sudo()
        email = cart.contact_email if 'contact_email' in cart._fields else False
        name = cart.guest_name if 'guest_name' in cart._fields else False

        if email:
            partner = Partner.search([('email', '=', email)], limit=1)
            if partner:
                return partner

        partner_vals = {
            'name': name or email or 'Guest',
            'email': email or False,
        }
        if 'phone' in Partner._fields and 'contact_phone' in cart._fields:
            partner_vals['phone'] = cart.contact_phone or False

        return Partner.create(partner_vals)

    def _compute_transaction_reference(self, provider):
        """Compute a unique reference for the payment transaction.

        Handles different Odoo versions where _compute_reference may
        have different signatures or may not exist.
        """
        Transaction = request.env['payment.transaction'].sudo()
        prefix = 'BE'

        for args in [
            {'provider_code': provider.code, 'prefix': prefix},
            (provider.code, prefix),
            (provider.code,),
            {'prefix': prefix},
        ]:
            try:
                if isinstance(args, dict):
                    return Transaction._compute_reference(**args)
                else:
                    return Transaction._compute_reference(*args)
            except TypeError:
                continue

        import uuid
        ref = f"{prefix}-{uuid.uuid4().hex[:12].upper()}"
        _logger.info("Generated fallback reference: %s", ref)
        return ref

    def _confirm_transaction_server_side(self, transaction):
        """Confirm a payment transaction server-side.

        The Odoo Demo provider (and other test-mode providers) rely on
        a frontend JavaScript flow that our custom controller does not
        use.  Without this step the transaction stays in ``draft``
        state and the return page shows "Payment was not successful".

        This method tries every known Odoo API for confirming a
        transaction, from newest to oldest.

        Each attempt runs inside its own SQL savepoint. If a method
        fails partway through a DB write, Postgres marks the whole
        transaction as aborted and refuses any further commands until
        a ROLLBACK happens - so without a savepoint here, one failed
        attempt would silently poison every later attempt (and the
        rest of the request) with
        ``psycopg2.errors.InFailedSqlTransaction``, even though the
        `except Exception` below looks like it safely moved on.
        """
        cr = request.env.cr
        for method_name in ('_set_done', 'action_done', '_set_state_done'):
            if hasattr(transaction, method_name):
                try:
                    with cr.savepoint():
                        getattr(transaction, method_name)()
                    _logger.info(
                        "Transaction %s confirmed via %s()",
                        transaction.id, method_name,
                    )
                    return True
                except Exception:
                    _logger.exception("%s() failed", method_name)

        try:
            with cr.savepoint():
                transaction.sudo().write({'state': 'done'})
            _logger.info(
                "Transaction %s confirmed via direct write(state=done)",
                transaction.id,
            )
            return True
        except Exception:
            _logger.exception("Direct write(state=done) failed")
            return False

    @http.route('/booking', type='http', auth='public', website=True, sitemap=True)
    def be_booking_search(self, property_id=None, **kwargs):
        """Render the booking engine search page."""
        property_rec = self._get_property(property_id)
        be_config = self._get_be_config(property_rec)

        # Pre-fill the date pair from the hotel's own business date and
        # its configured default length of stay, so the commonest search
        # is one click rather than two date pickers.
        today = (property_rec and property_rec.business_date) \
            or fields.Date.context_today(request.env.user)
        nights = (be_config and be_config.default_los) or 2

        values = {
            'property': property_rec,
            'properties': request.env['hospitality.property'].sudo().search([]),
            'be_config': be_config,
            'currency_symbol': self._be_currency_symbol(property_rec),
            'hero_url': self._be_hero_url(property_rec, be_config),
            'default_arrival': fields.Date.to_string(today),
            'default_departure': fields.Date.to_string(
                today + timedelta(days=nights)
            ),
        }
        return request.render('hospitality_booking_engine.be_search', values)

    @http.route('/booking/results', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def be_booking_results(self, property_id=None, arrival=None, departure=None,
                            adults=None, children=None, promo_code=None, **kwargs):
        """Display available rooms and rates matching the search criteria.
        Updates the visitor's search session, applies an optional promo
        code, retrieves available rate plans, calculates stay prices,
        and renders the search results page.
        """
        property_rec = self._get_property(property_id)
        cart = self._get_cart(property_rec)
        cart.write({
            'arrival': arrival or False,
            'departure': departure or False,
            'adults': int(adults or 1),
            'children': int(children or 0),
            'last_activity_at': fields.Datetime.now(),
        })
        if promo_code:
            cart._apply_promo_code(promo_code)

        be_config = self._get_be_config(property_rec)
        show_photos = self._be_flag(be_config, 'show_room_photos')
        show_amenities = self._be_flag(be_config, 'show_amenities')

        results = []
        arrival_date = fields.Date.from_string(arrival) if arrival else None
        departure_date = fields.Date.from_string(departure) if departure else None

        if arrival_date and departure_date:
            RateCode = request.env['hospitality.rate.code'].sudo()
            SpaceType = request.env['hospitality.space.type'].sudo()
            rate_codes = RateCode.search([
                '|', ('property_id', '=', property_rec.id), ('property_id', '=', False),
                ('state', '=', 'active'),
            ])
            space_types = SpaceType.search([
                '|', ('property_id', '=', property_rec.id), ('property_id', '=', False),
            ])

            occupancy = {'adults': int(adults or 1), 'children': int(children or 0)}
            for rate_code in rate_codes:
                for space_type in space_types:
                    try:
                        rate_info = rate_code._get_rate(
                            property_rec.id, space_type.id, rate_code.id,
                            arrival_date, departure_date, occupancy,
                        )
                    except Exception:
                        _logger.exception(
                            "rate_code._get_rate() failed for rate_code=%s "
                            "space_type=%s", rate_code.id, space_type.id,
                        )
                        continue

                    if not rate_info or rate_info.get('restrictions'):
                        continue
                    nightly = rate_info.get('nightly') or []
                    if not nightly or any(price is None for _d, price in nightly):
                        continue
                    total = sum(price for _d, price in nightly)

                    nights = (departure_date - arrival_date).days or 1
                    photos = self._be_space_type_photo_urls(space_type, limit=1) \
                        if show_photos else []

                    results.append({
                        'rate_code_id': rate_code.id,
                        'rate_code_name': rate_code.name,
                        'space_type_id': space_type.id,
                        'space_type_name': space_type.name,
                        'price_display': f"{total:.2f}",
                        'per_night_display': f"{total / nights:.2f}",
                        'nights': nights,
                        'meta': self._be_space_type_meta(space_type),
                        'amenities': self._be_amenity_names(space_type, limit=3)
                            if show_amenities else [],
                        'badges': [],
                        # The template has had an <img> slot all along;
                        # this was hardcoded False, so a room-type photo
                        # could be uploaded and no guest ever saw it.
                        # Served through our own route rather than
                        # /web/image: see be_space_type_photo below.
                        'photo_url': photos[0] if photos else False,
                    })

        values = {
            'property': property_rec,
            'be_config': be_config,
            'currency_symbol': self._be_currency_symbol(property_rec),
            'results': results,
            # Recap of what was actually searched, so the guest can see
            # which dates these prices belong to without going back.
            'search_summary': {
                'arrival': self._be_format_date(arrival),
                'departure': self._be_format_date(departure),
                'nights': (departure_date - arrival_date).days
                    if arrival_date and departure_date else 0,
                'adults': int(adults or 1),
                'children': int(children or 0),
                'promo_code': promo_code or '',
            },
        }
        return request.render('hospitality_booking_engine.be_results', values)

    @http.route(
        '/booking/space-type/<int:space_type_id>/photo',
        type='http', auth='public', website=True, readonly=True,
    )
    def be_space_type_photo(self, space_type_id, width=0, height=0, **kwargs):
        """Serve a space type's photo to an anonymous booker.

        NOT /web/image. That route goes through the ORM as the visitor,
        and hospitality.space.type is readable only by property users and
        above - there is no public or portal ACL anywhere in this suite.
        An anonymous guest would get the placeholder, which is how the
        booking engine ended up showing no photographs at all.

        Widening the model's ACL to base.group_public would hand every
        anonymous visitor ORM read on an operational model to fix one
        image, so the image is streamed here under sudo instead, with the
        checks that make it safe to do so:

          * the space type must be active, and
          * its property must have a booking engine configured - i.e. the
            property has deliberately been put up for public sale.

        A type that fails either check, or has no image, falls back to
        Odoo's own placeholder exactly as /web/image does.
        """
        space_type = request.env['hospitality.space.type'].sudo().browse(
            space_type_id
        ).exists()

        publishable = bool(space_type) and space_type.active
        if publishable and space_type.property_id:
            publishable = bool(request.env['hospitality.be.config'].sudo().search_count(
                [('property_id', '=', space_type.property_id.id)], limit=1
            ))

        return self._be_image_response(
            space_type if publishable else None, 'image', width, height,
        )

    @http.route(
        '/booking/space-type/<int:space_type_id>/gallery/<int:image_id>',
        type='http', auth='public', website=True, readonly=True,
    )
    def be_space_type_gallery_photo(self, space_type_id, image_id,
                                    width=0, height=0, **kwargs):
        """Serve one photo from a room type's gallery.

        Same reasoning as be_space_type_photo above. Both ids come off
        the URL, so this additionally checks that the image really does
        belong to the room type named beside it - otherwise the type id
        in the path would be decorative and any gallery image on the
        database could be fetched through a published type.
        """
        image = request.env['hospitality.space.type.image'].sudo().browse(
            image_id
        ).exists()
        space_type = request.env['hospitality.space.type'].sudo().browse(
            space_type_id
        ).exists()

        publishable = (
            bool(image) and bool(space_type)
            and image.space_type_id == space_type
            and space_type.active
            and (
                not space_type.property_id
                or self._be_is_publishable(space_type.property_id)
            )
        )
        return self._be_image_response(
            image if publishable else None, 'image_1920', width, height,
        )

    @http.route(
        '/booking/property/<int:property_id>/hero',
        type='http', auth='public', website=True, readonly=True,
    )
    def be_property_hero(self, property_id, width=0, height=0, **kwargs):
        """Serve a property's hero photograph for the search page.

        hospitality.property is no more readable by an anonymous visitor
        than hospitality.space.type is, so this follows the same pattern:
        published properties only, streamed under sudo, placeholder for
        everything else.
        """
        property_rec = request.env['hospitality.property'].sudo().browse(
            property_id
        ).exists()

        record, field_name = None, None
        if property_rec and property_rec.active \
                and self._be_is_publishable(property_rec):
            record, field_name = self._be_hero_source(property_rec)

        return self._be_image_response(record, field_name, width, height)

    @http.route('/booking/select/<int:rate_code_id>', type='http', auth='public',
                website=True, sitemap=False)
    def be_booking_select(self, rate_code_id, space_type_id=None,
                          property_id=None, **kwargs):
        """Display details for a selected room and rate.
        Calculates the total stay price for the selected rate plan,
        stores the user's selection in the session, and renders the
        room details page.
        """
        property_rec = self._get_property(property_id)
        rate_code = request.env['hospitality.rate.code'].sudo().browse(rate_code_id)
        space_type = request.env['hospitality.space.type'].sudo().browse(
            int(space_type_id)
        ) if space_type_id else request.env['hospitality.space.type'].sudo().browse()

        price_display = ''
        cart = self._get_cart(property_rec)
        if cart.arrival and cart.departure and space_type:
            try:
                arrival_date = fields.Date.from_string(cart.arrival) \
                    if isinstance(cart.arrival, str) else cart.arrival
                departure_date = fields.Date.from_string(cart.departure) \
                    if isinstance(cart.departure, str) else cart.departure
                rate_info = rate_code._get_rate(
                    property_rec.id, space_type.id, rate_code.id,
                    arrival_date, departure_date,
                    {'adults': cart.adults or 1, 'children': cart.children or 0},
                )
                nightly = (rate_info or {}).get('nightly') or []
                if nightly and not any(price is None for _d, price in nightly) \
                        and not (rate_info or {}).get('restrictions'):
                    total = sum(price for _d, price in nightly)
                    price_display = f"{total:.2f}"
            except Exception:
                _logger.exception(
                    "Could not price rate_code=%s space_type=%s",
                    rate_code_id, space_type_id,
                )

        request.session['be_pending_rate_code_id'] = rate_code_id
        request.session['be_pending_space_type_id'] = space_type.id

        be_config = self._get_be_config(property_rec)
        values = {
            'property': property_rec,
            'be_config': be_config,
            'currency_symbol': self._be_currency_symbol(property_rec),
            'space_type': space_type,
            # These two were hardcoded empty, so the gallery and the
            # amenity list rendered as empty markup on every room.
            'photos': self._be_space_type_photo_urls(space_type)
                if self._be_flag(be_config, 'show_room_photos') else [],
            'amenities': self._be_amenity_names(space_type)
                if self._be_flag(be_config, 'show_amenities') else [],
            'room_meta': self._be_space_type_meta(space_type),
            'stay_summary': {
                'arrival': self._be_format_date(cart.arrival),
                'departure': self._be_format_date(cart.departure),
            } if cart.arrival and cart.departure else None,
            'price_display': price_display,
        }
        return request.render('hospitality_booking_engine.be_room_detail', values)

    @http.route('/booking/cart', type='http', auth='public', website=True,
                methods=['GET', 'POST'], csrf=True)
    def be_booking_cart(self, property_id=None, adults=None, **kwargs):
        """Display and manage the visitor's booking cart.
        GET requests display the current cart contents, available
        upsells, and booking totals. POST requests store the selected
        room and rate in the current search session.
        """
        property_rec = self._get_property(property_id)
        cart = self._get_cart(property_rec)

        if request.httprequest.method == 'POST':
            rate_code_id = request.session.pop('be_pending_rate_code_id', None)
            space_type_id = request.session.pop('be_pending_space_type_id', None)
            vals = {'last_activity_at': fields.Datetime.now()}
            if rate_code_id:
                vals['selected_rate_code_id'] = rate_code_id
            if space_type_id:
                vals['selected_space_type_id'] = space_type_id
            if adults:
                vals['adults'] = int(adults)
            cart.write(vals)
            return request.redirect('/booking/cart')

        totals = cart._cart_totals()
        Upsell = request.env['hospitality.be.upsell'].sudo()
        upsells = Upsell.search([('property_id', '=', property_rec.id)]) \
            if 'property_id' in Upsell._fields else Upsell.search([])

        values = {
            'property': property_rec,
            'be_config': self._get_be_config(property_rec),
            'currency_symbol': self._be_currency_symbol(property_rec),
            'cart_lines': cart._get_cart_lines(),
            'upsells': [{
                'id': u.id,
                'name': u.name,
                'price_display': f"{u.price:.2f}" if 'price' in u._fields else '',
            } for u in upsells],
            'subtotal_display': totals.get('subtotal_display'),
            'taxes_display': totals.get('taxes_display'),
            'total_display': totals.get('total_display'),
        }
        return request.render('hospitality_booking_engine.be_cart', values)

    @http.route('/booking/cart/apply_promo', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    def be_booking_apply_promo(self, property_id=None, promo_code=None, **kwargs):
        """Apply a promotional code to the current booking cart."""
        property_rec = self._get_property(property_id)
        cart = self._get_cart(property_rec, create=False)
        if cart.exists() and promo_code:
            cart._apply_promo_code(promo_code)
        return request.redirect('/booking/cart')

    @http.route('/booking/cart/add_upsell', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    def be_booking_add_upsell(self, property_id=None, upsell_id=None, **kwargs):
        """Add an upsell item to the current booking cart."""
        property_rec = self._get_property(property_id)
        cart = self._get_cart(property_rec, create=False)
        if cart.exists() and upsell_id:
            cart._add_upsell(int(upsell_id))
        return request.redirect('/booking/cart')

    @http.route('/booking/checkout', type='http', auth='public', website=True,
                methods=['GET', 'POST'], csrf=True)
    def be_booking_checkout(self, property_id=None, guest_name=None,
                             guest_email=None, guest_phone=None,
                             guest_nationality_id=None, guest_notes=None,
                             payment_error_msg=None, **kwargs):
        """Render the checkout page.
        Stores guest details submitted from the checkout form and
        displays the available payment providers for completing the
        booking.
        """
        property_rec = self._get_property(property_id)
        cart = self._get_cart(property_rec)

        if request.httprequest.method == 'POST':
            cart.write({
                'guest_name': guest_name,
                'contact_email': guest_email,
                'contact_phone': guest_phone,
                'guest_nationality_id': int(guest_nationality_id) if guest_nationality_id else False,
                'guest_notes': guest_notes,
                'last_activity_at': fields.Datetime.now(),
            })
            return request.redirect('/booking/checkout')

        payment_providers = self._payment_providers(property_rec)

        values = {
            'property': property_rec,
            'be_config': self._get_be_config(property_rec),
            'countries': request.env['res.country'].sudo().search([]),
            **self._be_checkout_summary(property_rec, cart),
            'payment_providers': payment_providers,
            'payment_error': bool(payment_error_msg),
            'payment_error_msg': payment_error_msg or '',
        }
        return request.render('hospitality_booking_engine.be_checkout', values)

    @http.route('/booking/checkout/pay', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    def be_booking_pay(self, property_id=None, payment_provider_id=None,
                        guest_name=None, guest_email=None, guest_phone=None,
                        guest_nationality_id=None, guest_notes=None, **kwargs):
        """Process the checkout payment.

        Every step is wrapped in try/except so that if anything fails
        we redirect back to the checkout page with the error message
        instead of showing a raw 500 page.
        """
        try:
            property_rec = self._get_property(property_id)
            cart = self._get_cart(property_rec, create=False)
            if not cart.exists() or not payment_provider_id:
                return request.redirect('/booking/checkout')

            cart.write({
                'guest_name': guest_name,
                'contact_email': guest_email,
                'contact_phone': guest_phone,
                'guest_nationality_id': int(guest_nationality_id) if guest_nationality_id else False,
                'guest_notes': guest_notes,
            })

            provider = request.env['payment.provider'].sudo().browse(
                int(payment_provider_id)
            )
            _logger.info("PAY: provider=%s (id=%s, code=%s, state=%s)",
                         provider.name, provider.id, provider.code, provider.state)

            totals = cart._cart_totals()
            _logger.info("PAY: totals=%s", totals)

            partner = self._get_or_create_partner_for_cart(cart)
            _logger.info("PAY: partner=%s (id=%s)", partner.name, partner.id)

            payment_method = self._get_payment_method_for_provider(provider)
            _logger.info("PAY: payment_method=%s",
                         payment_method.name if payment_method else None)
            if not payment_method:
                raise ValidationError(
                    _("No payment method is configured for the payment "
                      "provider '%s'. Please ask the site administrator "
                      "to link a payment method to it (Settings > "
                      "Payment Providers), or choose a different payment "
                      "option.") % provider.name
                )

            reference = self._compute_transaction_reference(provider)
            _logger.info("PAY: reference=%s", reference)

            tx_vals = {
                'provider_id': provider.id,
                'amount': totals.get('total') or 0.0,
                'currency_id': totals.get('currency_id'),
                'partner_id': partner.id,
                'reference': reference,
                'landing_route': '/booking/return',
            }
            if payment_method:
                tx_vals['payment_method_id'] = payment_method.id

            _logger.info("PAY: tx_vals keys=%s", list(tx_vals.keys()))

            transaction = request.env['payment.transaction'].sudo().create(tx_vals)
            _logger.info("PAY: transaction created id=%s state=%s",
                         transaction.id, transaction.state)

            cart.write({
                'payment_provider_id': provider.id,
                'payment_transaction_id': transaction.id,
            })

            redirect_url = '/booking/return'
            use_server_side_confirm = False

            try:
                with request.env.cr.savepoint():
                    rendering_values = transaction._get_processing_values()
                api_url = rendering_values.get('api_url') or ''
                _logger.info("PAY: _get_processing_values api_url=%r", api_url)

                if api_url and api_url.startswith('http'):
                    redirect_url = api_url
                else:
                    use_server_side_confirm = True
            except Exception:
                _logger.exception("PAY: _get_processing_values() failed")
                use_server_side_confirm = True

            if use_server_side_confirm:
                _logger.info("PAY: confirming server-side for provider '%s'",
                             provider.code)
                self._confirm_transaction_server_side(transaction)
                _logger.info("PAY: transaction state after confirm=%s",
                             transaction.state)

            return request.redirect(redirect_url)

        except Exception as exc:
            error_msg = str(exc)
            _logger.error(
                "PAY: UNHANDLED ERROR in be_booking_pay:\n%s\n%s",
                error_msg, traceback.format_exc(),
            )
            return request.redirect(
                f'/booking/checkout?payment_error_msg={error_msg}'
            )

    @http.route('/booking/return', type='http', auth='public',
                website=True, sitemap=False)
    def be_booking_return(self, property_id=None, **kwargs):
        """Handle the return from the payment provider.
        Validates the payment result, finalizes the reservation when the
        payment succeeds, and displays either the booking confirmation
        page or an appropriate payment/error page.
        """
        property_rec = self._get_property(property_id)
        cart = self._get_cart(property_rec, create=False)
        if not cart.exists():
            return request.redirect('/booking')

        transaction = cart.payment_transaction_id
        success = bool(transaction) and transaction.state in ('done', 'authorized')

        _logger.info(
            "RETURN: transaction=%s state=%s success=%s",
            transaction.id if transaction else None,
            transaction.state if transaction else None,
            success,
        )

        if success and not cart.reservation_id:
            finalize_ok = False
            try:
                with request.env.cr.savepoint():
                    cart._finalize_booking()
                    finalize_ok = True
                    _logger.info("RETURN: _finalize_booking() succeeded")
            except Exception:
                _logger.exception(
                    "RETURN: _finalize_booking() failed inside savepoint "
                    "— transaction rolled back safely, DB is clean."
                )

            if not finalize_ok:
                try:
                    payment_providers = self._payment_providers(property_rec)
                except Exception:
                    _logger.exception(
                        "Could not load payment providers for error page"
                    )
                    payment_providers = request.env['payment.provider'].sudo().browse()

                values = {
                    'property': property_rec,
                    'be_config': self._get_be_config(property_rec),
                    'countries': request.env['res.country'].sudo().search([]),
                    **self._be_checkout_summary(property_rec, cart),
                    'payment_providers': payment_providers,
                    'payment_error': True,
                    'payment_error_msg': (
                        'Payment was successful but the reservation '
                        'could not be created automatically. Please '
                        'contact support with your payment reference.'
                    ),
                }
                return request.render(
                    'hospitality_booking_engine.be_checkout', values
                )

        if not success:
            try:
                payment_providers = self._payment_providers(property_rec)
            except Exception:
                _logger.exception(
                    "Could not load payment providers for error page"
                )
                payment_providers = request.env['payment.provider'].sudo().browse()

            values = {
                'property': property_rec,
                'be_config': self._get_be_config(property_rec),
                'countries': request.env['res.country'].sudo().search([]),
                **self._be_checkout_summary(property_rec, cart),
                'payment_providers': payment_providers,
                'payment_error': True,
                'payment_error_msg': 'Payment was not successful. Please try again.',
            }
            return request.render('hospitality_booking_engine.be_checkout', values)

        reservation = cart.reservation_id
        totals = cart._cart_totals()
        values = {
            'property': property_rec,
            'be_config': self._get_be_config(property_rec),
            'currency_symbol': self._be_currency_symbol(property_rec),
            'reservation_ref': reservation.name if 'name' in reservation._fields else str(reservation.id),
            'arrival': self._be_format_date(cart.arrival),
            'departure': self._be_format_date(cart.departure),
            'total_display': totals.get('total_display'),
        }
        return request.render('hospitality_booking_engine.be_confirmation', values)

    @http.route('/booking/lookup', type='http', auth='public', website=True,
                methods=['GET', 'POST'], csrf=True, sitemap=True)
    def be_booking_lookup(self, ref=None, email=None, **kwargs):
        """Look up an existing reservation.
        Searches for a reservation using the supplied reservation
        reference and guest email address, then displays the booking
        details if a matching reservation is found.
        """
        lookup_result = None
        if ref and email:
            Reservation = request.env['hospitality.reservation'].sudo()
            name_field = 'name' if 'name' in Reservation._fields else None
            domain = [('partner_id.email', '=', email)]
            if name_field:
                domain.append((name_field, '=', ref))
            reservation = Reservation.search(domain, limit=1)
            if reservation:
                lookup_result = {
                    'cart_lines': [{
                        'id': reservation.id,
                        'space_type_name': getattr(reservation.space_type_id, 'name', ''),
                        'arrival': getattr(reservation, 'arrival', ''),
                        'departure': getattr(reservation, 'departure', ''),
                        'adults': getattr(reservation, 'adults', ''),
                        'price_display': '',
                    }],
                    'upsells': [],
                    'subtotal_display': '',
                    'taxes_display': '',
                    'total_display': '',
                }

        property_rec = self._get_property()
        values = {
            'property': property_rec,
            'be_config': self._get_be_config(property_rec),
            'currency_symbol': self._be_currency_symbol(property_rec),
            'lookup_result': lookup_result,
        }
        return request.render('hospitality_booking_engine.be_lookup', values)