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
    'name': "Hospitality Management",
    'version': '19.0.1.1.0',
    'category': 'Hospitality',
    'summary': "Hotel PMS foundation for Odoo: multi-property setup, brands, business date, policies and the backend theme.",
    'description': """
Hospitality Management - Base
=============================
Foundation module of the Hospitality Management suite, a complete hotel property management system for Odoo. It carries everything the other modules build on: properties and brands, per-property currency, timezone, check-in and check-out times and an independent business date, user-to-property binding and property switching, market segments, source codes, transaction codes, cancellation and deposit policies, activity tracing, encrypted fields, automated sequences and the suite's ink-and-brass backend theme. Install it first whether you run a single hotel, a multi-property group or a resort chain.

Key Features
------------
* Multi-property and multi-brand structure, each property with its own currency, timezone and sequences
* Independent business date per property, rolled forward by night audit rather than the system clock
* User-to-property binding so staff only see the properties they operate in
* Market segments, source codes and transaction codes shared across the suite
* Cancellation and deposit policies reused by reservations and folios
* Property photo galleries and a modern property register
* Backend theme for the login, app drawer and navbar rail
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': "https://www.cybrosys.com",
    'depends': [
        'base',
        'mail',
        'web',
        'account',
        'product',
        # The login brand panel inherits auth_signup.login to reword the
        # password-reset link. Came in with hospitality_theme.
        'auth_signup',
    ],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'data/hospitality_config_data.xml',
        'data/hospitality_policies_data.xml',
        'data/ir_cron.xml',
        'data/theme_params.xml',
        'data/home_action.xml',
        'views/hospitality_brand_views.xml',
        'views/hospitality_property_image_views.xml',
        'views/hospitality_property_views.xml',
        'views/res_users_views.xml',
        'views/hospitality_market_segment_views.xml',
        'views/hospitality_source_code_views.xml',
        'views/hospitality_transaction_code_views.xml',
        'views/hospitality_cancellation_policy_views.xml',
        'views/hospitality_deposit_policy_views.xml',
        'views/hospitality_activity_trace_views.xml',
        'views/hospitality_operations_views.xml',
        'views/res_config_settings_views.xml',
        'views/login_templates.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/hospitality_demo.xml',
    ],
    'assets': {
        # Prepended: Odoo's own definitions use !default, so ours only
        # win if they are seen first.
        'web._assets_primary_variables': [
            'hospitality_base/static/src/scss/variables.scss',
        ],
        'web.assets_backend': [
            'hospitality_base/static/src/js/property_switcher.js',
            'hospitality_base/static/src/scss/property_switcher.scss',
            'hospitality_base/static/src/scss/property_gallery.scss',
            'hospitality_base/static/src/scss/property_kanban.scss',
            'hospitality_base/static/src/xml/property_switcher.xml',
            # --- backend theme (was hospitality_theme) --------------------
            # Appended, not interleaved: as a separate module the theme
            # loaded after this one, so its rules won every tie. Keeping
            # it last preserves that cascade exactly.
            'hospitality_base/static/src/scss/mixins.scss',
            'hospitality_base/static/src/scss/chrome.scss',
            'hospitality_base/static/src/scss/home.scss',
            'hospitality_base/static/src/xml/navbar.xml',
            'hospitality_base/static/src/xml/apps_menu.xml',
            'hospitality_base/static/src/xml/home.xml',
            'hospitality_base/static/src/xml/business_date_systray.xml',
            'hospitality_base/static/src/js/app_palette.js',
            'hospitality_base/static/src/js/navbar_patch.js',
            'hospitality_base/static/src/js/home.js',
            'hospitality_base/static/src/js/business_date_systray.js',
        ],
        'web.assets_frontend': [
            'hospitality_base/static/src/scss/mixins.scss',
            'hospitality_base/static/src/scss/login.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'external_dependencies': {
        'python': ['cryptography'],
    },
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
