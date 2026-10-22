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
    'name': "Hospitality Management - Property",
    'version': '19.0.1.0.0',
    'category': 'Hospitality',
    'summary': "Hotel room inventory for Odoo: buildings, floors, sections, room types, amenities, room status and floor plan.",
    'description': """
Hospitality Management - Property
=================================
Room and space inventory for the Hospitality Management suite. Model the physical hotel as buildings, floors and sections, define room types with occupancy, bed configuration, size, amenities and photo galleries, and manage every room with a live housekeeping status that the whole suite reads from. A colour-coded floor plan shows room status at a glance, and virtual rooms cover inventory that is not sold.

Key Features
------------
* Buildings, floors and sections per property
* Room types with occupancy, bed configuration, size and photo gallery
* Rooms with live housekeeping status, out of order and out of service handling
* Virtual rooms for inventory that is not sold
* Shared amenity and feature catalogue
* Floor plan view colour-coded by room status
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['hospitality_base', 'web'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/hospitality_space_feature_data.xml',
        'views/hospitality_building_views.xml',
        'views/hospitality_floor_views.xml',
        'views/hospitality_section_views.xml',
        'views/hospitality_space_feature_views.xml',
        'views/hospitality_space_type_image_views.xml',
        'views/hospitality_space_type_views.xml',
        'views/hospitality_space_views.xml',
        'views/floor_plan_action.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/hospitality_property_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hospitality_property/static/src/scss/floor_plan_view.scss',
            'hospitality_property/static/src/scss/room_kanban.scss',
            'hospitality_property/static/src/xml/floor_plan_view.xml',
            'hospitality_property/static/src/js/floor_plan_view.js',
        ],
        'web.assets_tests': [
            'hospitality_property/static/src/js/floor_plan_tours.js',
        ],
    },
    'images': ['static/description/banner.jpg'],
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}