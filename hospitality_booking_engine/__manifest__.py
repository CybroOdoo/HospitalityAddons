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
{
    'name': "Hospitality Management - Booking Engine",
    'version': '19.0.1.0.0',
    'category': 'Hospitality/Booking Engine',
    'summary': "Direct hotel booking engine for Odoo websites: live availability, promo codes, upsells and payment-provider checkout.",
    'description': """
Hospitality Management - Booking Engine
=======================================
Commission-free direct booking engine for the Hospitality Management suite. Puts a branded hotel booking search on your own website using the property's hero image and colour, prices real rooms online with the same rate engine the front desk uses, offers promo codes and upsells, takes payment through your configured Odoo payment providers, and sends a confirmation with a self-service booking lookup. Every online room reservation lands straight in the PMS, with no OTA commission on the booking.

Key Features
------------
* Public search and live availability on the website
* Pricing from the same rate engine the desk uses
* Promo codes with validity rules
* Upsells offered during checkout
* Checkout through Odoo payment providers
* Confirmation email and self-service booking lookup
* Per-property theme colour and hero image
    """,
    'author': "Cybrosys Techno Solutions",
    'company': "Cybrosys Techno Solutions",
    'maintainer': "Cybrosys Techno Solutions",
    'website': "https://www.cybrosys.com",
    'depends': [
        'hospitality_property',
        'hospitality_rate',
        'hospitality_reservation',
        'hospitality_folio',
        'website',
        'payment',
        'mail',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'data/website_menu_data.xml',
        'views/hospitality_be_config_views.xml',
        'views/hospitality_be_promo_code_views.xml',
        'views/hospitality_be_upsell_views.xml',
        'views/hospitality_be_search_session_views.xml',
        'views/templates.xml',
        'views/booking_engine_menus.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'hospitality_booking_engine/static/src/scss/booking_engine_base.scss',
            'hospitality_booking_engine/static/src/scss/booking_engine_theme_light.scss',
            'hospitality_booking_engine/static/src/scss/booking_engine_theme_dark.scss',
            'hospitality_booking_engine/static/src/scss/booking_engine_theme_brand.scss',
        ],
        'web.assets_tests': [
            'hospitality_booking_engine/static/tests/tours/booking_engine_tour.js',
            'hospitality_booking_engine/static/tests/tours/booking_engine_full_flow_tour.js',
        ],
    },
    'demo': [
        'demo/hospitality_booking_engine_demo.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
