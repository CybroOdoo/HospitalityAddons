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
"""
PROP-02 Tests — Building / Floor / Section hierarchy.

FIX: All test env calls now use .sudo() so the _check_property_access
mixin in hospitality_mixin_property does not block record creation.
The mixin checks that the current user is assigned to the property
being written to. In test context the user is __system__ with no
property assignments, so every write was raising AccessError.

Using sudo() makes tests run as the internal superuser (uid=1)
which bypasses property-level record rules — correct for unit tests
that are testing model logic, not access control.
"""

from odoo.tests.common import TransactionCase


class TestBuildingFloorSection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create properties as superuser
        Property = cls.env['hospitality.property'].with_user(1)

        cls.property_a = Property.create({
            'name': 'Property Alpha',
            'code': 'ALPHA',
        })
        cls.property_b = Property.create({
            'name': 'Property Beta',
            'code': 'BETA',
        })

        for prop in (cls.property_a, cls.property_b):
            for field in ('user_ids', 'allowed_user_ids', 'manager_ids', 'member_ids'):
                if field in cls.env['hospitality.property']._fields:
                    prop.with_user(1).write({field: [(4, 1)]})  # link uid=1
                    break

    # ---------------------------------------------------------
    # Test 1 : Building Creation
    # ---------------------------------------------------------
    def test_01_building_creation(self):
        """Building should be created successfully."""

        building = self.env['hospitality.building'].sudo().create({
            'name': 'Tower A',
            'code': 'TWR-A',
            'property_id': self.property_a.id,
            'sequence': 5,
        })

        self.assertEqual(building.property_id, self.property_a)
        self.assertEqual(building.code, 'TWR-A')
        self.assertTrue(building.active)

    # ---------------------------------------------------------
    # Test 2 : Floor & Section Creation
    # ---------------------------------------------------------
    def test_02_floor_section_creation(self):
        """Floor and Section should be linked to the building."""

        building = self.env['hospitality.building'].sudo().create({
            'name': 'Block B',
            'code': 'BLK-B',
            'property_id': self.property_a.id,
        })

        floor = self.env['hospitality.floor'].sudo().create({
            'name': 'Ground Floor',
            'code': 'GF',
            'building_id': building.id,
        })

        section = self.env['hospitality.section'].sudo().create({
            'name': 'West Wing',
            'code': 'WW',
            'building_id': building.id,
        })

        self.assertEqual(floor.building_id, building)
        self.assertEqual(section.building_id, building)
        self.assertIn(floor, building.floor_ids)
        self.assertIn(section, building.section_ids)

    # ---------------------------------------------------------
    # Test 3 : Duplicate Building Code
    # ---------------------------------------------------------
    def test_03_building_code_unique_per_property(self):
        """Duplicate building code under the same property must be rejected."""

        self.env['hospitality.building'].sudo().create({
            'name': 'Original Building',
            'code': 'DUP',
            'property_id': self.property_a.id,
        })

        with self.assertRaises(Exception):
            self.env['hospitality.building'].sudo().create({
                'name': 'Duplicate Building',
                'code': 'DUP',
                'property_id': self.property_a.id,
            })

    # ---------------------------------------------------------
    # Test 4 : Same code in different property (should succeed)
    # ---------------------------------------------------------
    def test_04_same_code_different_property(self):
        """Same building code in a different property must be allowed."""

        self.env['hospitality.building'].sudo().create({
            'name': 'Building A',
            'code': 'COMMON',
            'property_id': self.property_a.id,
        })

        building_b = self.env['hospitality.building'].sudo().create({
            'name': 'Building B',
            'code': 'COMMON',
            'property_id': self.property_b.id,
        })

        self.assertTrue(building_b)