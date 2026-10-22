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
RATE-05 — Tests for hospitality.package

Tests:
  1. test_total_value_recomputes_on_add_inclusion
  2. test_seed_packages_present
  3. test_uniqueness_per_property
"""

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from psycopg2 import IntegrityError


@tagged('post_install', '-at_install', 'hospitality_rate')
class TestHospitalityPackage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Property ─────────────────────────────────────────────────
        cls.property = cls.env['hospitality.property'].create({
            'name': 'Test Hotel',
            'code': 'TH005',
        })

        # ── Transaction Codes (with all required fields) ─────────────
        cls.tc_breakfast = cls.env['hospitality.transaction.code'].create({
            'name': 'Breakfast Test',
            'code': 'BRK_TEST',
            'category': 'fnb',
            'sign': 'debit',
        })

        cls.tc_spa = cls.env['hospitality.transaction.code'].create({
            'name': 'Spa Credit Test',
            'code': 'SPA_TEST',
            'category': 'other_revenue',
            'sign': 'debit',
        })

        # ── Model aliases ────────────────────────────────────────────
        cls.Package = cls.env['hospitality.package']
        cls.Inclusion = cls.env['hospitality.package.inclusion']

    # ══════════════════════════════════════════════════════════════════════
    # TEST 1: total_value recomputes when inclusions are added
    # ══════════════════════════════════════════════════════════════════════

    def test_total_value_recomputes_on_add_inclusion(self):
        """total_value = sum(qty × value) across all inclusions.
        Adding or modifying inclusions should update total_value."""

        # Create package with one inclusion
        package = self.Package.create({
            'name': 'Test Package',
            'code': 'TPKG',
            'property_id': self.property.id,
            'inclusion_ids': [
                (0, 0, {
                    'transaction_code_id': self.tc_breakfast.id,
                    'qty': 1.0,
                    'value': 15.0,
                    'posting_rhythm': 'per_night',
                }),
            ],
        })

        # total_value = 1 × 15 = 15
        self.assertEqual(package.total_value, 15.0)

        # Add a second inclusion
        self.Inclusion.create({
            'package_id': package.id,
            'transaction_code_id': self.tc_spa.id,
            'qty': 2.0,
            'value': 25.0,
            'posting_rhythm': 'per_stay',
        })

        # Refresh computed field
        package.invalidate_recordset(['total_value'])

        # total_value = (1 × 15) + (2 × 25) = 15 + 50 = 65
        self.assertEqual(package.total_value, 65.0)

        # Modify qty of first inclusion
        first_inclusion = package.inclusion_ids.filtered(
            lambda i: i.transaction_code_id == self.tc_breakfast
        )
        first_inclusion.write({'qty': 3.0})

        package.invalidate_recordset(['total_value'])

        # total_value = (3 × 15) + (2 × 25) = 45 + 50 = 95
        self.assertEqual(package.total_value, 95.0)

    # ══════════════════════════════════════════════════════════════════════
    # TEST 2: Seed packages present
    # ══════════════════════════════════════════════════════════════════════

    def test_seed_packages_present(self):
        """Seed data should create BB and HONEYMOON packages
        with correct inclusions."""

        # BB package
        bb = self.Package.search([('code', '=', 'BB')], limit=1)
        self.assertTrue(bb, "BB package should exist from seed data.")
        self.assertEqual(len(bb.inclusion_ids), 1,
                         "BB should have 1 inclusion.")
        self.assertEqual(bb.inclusion_ids[0].value, 15.0)
        self.assertEqual(bb.inclusion_ids[0].posting_rhythm,
                         'per_pax_per_night')
        # total_value = 1 × 15 = 15
        self.assertEqual(bb.total_value, 15.0)

        # HONEYMOON package
        hm = self.Package.search([('code', '=', 'HONEYMOON')], limit=1)
        self.assertTrue(hm, "HONEYMOON package should exist from seed data.")
        self.assertEqual(len(hm.inclusion_ids), 2,
                         "HONEYMOON should have 2 inclusions.")
        # total_value = (1 × 15) + (1 × 50) = 65
        self.assertEqual(hm.total_value, 65.0)

    # ══════════════════════════════════════════════════════════════════════
    # TEST 3: Code uniqueness per property
    # ══════════════════════════════════════════════════════════════════════

    def test_uniqueness_per_property(self):
        """Same code + same property should raise IntegrityError.
        Same code + different property should be allowed."""

        self.Package.create({
            'name': 'Unique Test A',
            'code': 'UNIQ',
            'property_id': self.property.id,
        })

        # Same code, same property -> should fail
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.Package.create({
                    'name': 'Unique Test B',
                    'code': 'UNIQ',
                    'property_id': self.property.id,
                })

        # Same code, different property -> should succeed
        property_2 = self.env['hospitality.property'].create({
            'name': 'Hotel Two',
            'code': 'HT002',
        })
        self.Package.create({
            'name': 'Unique Test C',
            'code': 'UNIQ',
            'property_id': property_2.id,
        })

        # Same code, no property (global) -> should succeed
        self.Package.create({
            'name': 'Unique Test D',
            'code': 'UNIQ',
        })