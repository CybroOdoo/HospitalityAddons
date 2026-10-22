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
    "name": "Hospitality Management - Folio",
    "version": '19.0.1.0.0',
    "category": "Hospitality",
    "summary": "Hotel guest folio and billing for Odoo: charges, payments, folio windows, routing, deposits, allowances and city ledger.",
    'description': """
Hospitality Management - Folio
==============================
Guest folio and billing for the Hospitality Management suite. Every charge and payment for a stay sits on a hotel folio split into windows, with routing rules that send selected charges to a company, travel agent or another folio, deposits taken up front, allowances and write-offs with an audit trail, and transfer of outstanding balances to accounts receivable at check-out. Folio routing, deposits and city ledger settlement connect guest billing to Odoo accounting and invoicing.

Key Features
------------
* Folios with multiple windows per stay
* Charge and payment posting
* Routing rules by company, agent or folio
* Deposits, allowances and write-offs
* Transfer to accounts receivable (city ledger)
* Full transaction history per folio
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    "depends": [
        "hospitality_reservation",
        "account",
    ],
    "data": [
        "security/security_groups.xml",
        "security/property_record_rules.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/folio_transaction_codes.xml",
        "views/folio_transaction_code_views.xml",
        "views/folio_line_views.xml",
        "views/folio_deposit_views.xml",
        "views/folio_allowance_views.xml",
        "views/folio_routing_views.xml",
        "views/folio_ar_views.xml",
        "views/folio_views.xml",
        "report/report_folio_tape.xml",
        "wizards/folio_wizard_views.xml",
    ],
    "demo": [
        'demo/demo_folios.xml',
    ],
    'images': ['static/description/banner.jpg'],
    "license": 'LGPL-3',
    "installable": True,
    "auto_install": False,
    "application": False,

}
