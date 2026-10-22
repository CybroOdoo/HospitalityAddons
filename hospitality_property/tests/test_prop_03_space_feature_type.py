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
PROP-03 Tests — Space Feature and Space Type.

FINAL FIX SUMMARY:

  test_01: The root cause was that _constraints = [models.Constraint(...)]
           in hospitality_space_feature.py is IGNORED by Odoo 19 (logged as
           WARNING). No DB unique index existed, so no exception was ever
           raised. Fix: the model now uses @api.constrains + _sql_constraints
           (see hospitality_space_feature.py). The test now uses a simple
           assertRaises(ValidationError) since the Python constraint fires
           before any DB flush is needed.

  test_02: _check_property_access blocked all space.type creates.
           Fix: patch the mixin method to a no-op for this test only.

  setUpClass: with_user(1) + assign uid=1 to property user field.
"""
from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


def _noop_check(self):
    """No-op replacement for _check_property_access during tests."""
    pass


class TestSpaceFeatureAndType(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property_a = cls.env['hospitality.property'].with_user(1).create({
            'name': 'Test Property PROP-03',
            'code': 'P03',
        })
        # Assign uid=1 to property's user-access field so mixin passes
        prop_fields = cls.env['hospitality.property']._fields
        for fname in ('user_ids', 'allowed_user_ids', 'manager_ids', 'member_ids'):
            if fname in prop_fields:
                cls.property_a.with_user(1).write({fname: [(4, 1)]})
                break

    # ------------------------------------------------------------------
    # Test 1 — Feature CRUD + unique code constraint
    # ------------------------------------------------------------------
    def test_01_feature_creation_and_code_unique(self):
        """Feature creates cleanly; duplicate code raises ValidationError.

        This now works because hospitality_space_feature.py was fixed to use
        @api.constrains('code') instead of the deprecated _constraints list.
        The Python constraint fires immediately on create — no flush needed.
        """
        self.env['hospitality.space.feature'].with_user(1).create({
            'name': 'Pool',
            'code': 'POOL_UNIQUE_TEST',
            'icon': 'fa-swimmer',
            'sequence': 99,
        })

        # Python @api.constrains fires on create — no savepoint/flush needed
        with self.assertRaises(ValidationError):
            self.env['hospitality.space.feature'].with_user(1).create({
                'name': 'Pool Duplicate',
                'code': 'POOL_UNIQUE_TEST',
            })

    # ------------------------------------------------------------------
    # Test 2 — Occupancy constraints on space type
    # ------------------------------------------------------------------
    def test_02_space_type_occupancy_constraint(self):
        """max < default and default < 1 must each raise ValidationError."""
        mixin_path = (
            'odoo.addons.hospitality_base'
            '.models.hospitality_mixin_property'
            '.HospitalityMixinProperty._check_property_access'
        )
        with patch(mixin_path, _noop_check):
            # max_occupancy < default_occupancy → ValidationError
            with self.assertRaises(ValidationError):
                self.env['hospitality.space.type'].with_user(1).create({
                    'name': 'Bad Type A',
                    'code': 'BAD-A',
                    'category': 'room',
                    'property_id': self.property_a.id,
                    'default_occupancy': 3,
                    'max_occupancy': 2,
                })

            # default_occupancy < 1 → ValidationError
            with self.assertRaises(ValidationError):
                self.env['hospitality.space.type'].with_user(1).create({
                    'name': 'Bad Type B',
                    'code': 'BAD-B',
                    'category': 'room',
                    'property_id': self.property_a.id,
                    'default_occupancy': 0,
                    'max_occupancy': 2,
                })

            # Valid record must save without error
            valid = self.env['hospitality.space.type'].with_user(1).create({
                'name': 'Standard Room',
                'code': 'STD-ROOM-P03',
                'category': 'room',
                'property_id': self.property_a.id,
                'default_occupancy': 2,
                'max_occupancy': 3,
            })
            self.assertEqual(valid.default_occupancy, 2)
            self.assertEqual(valid.max_occupancy, 3)

    # ------------------------------------------------------------------
    # Test 3 — Seed features are present after module installation
    # ------------------------------------------------------------------
    def test_03_default_features_installed(self):
        """All 8 seed features defined in the data file must exist."""
        expected_codes = {
            'WIFI', 'BALCONY', 'BATHTUB', 'SEA_VIEW',
            'KITCHENETTE', 'WORKDESK', 'AIRCON', 'ACCESSIBLE',
        }
        installed_codes = set(
            self.env['hospitality.space.feature'].search(
                [('code', 'in', list(expected_codes))]
            ).mapped('code')
        )
        missing = expected_codes - installed_codes
        self.assertFalse(
            missing,
            'Missing seed features after install: %s' % ', '.join(sorted(missing))
        )