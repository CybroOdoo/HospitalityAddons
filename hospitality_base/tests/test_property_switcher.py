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

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'hospitality')
class TestPropertySwitcher(TransactionCase):
    """BASE-03 — res.users / res.company inheritance + property switcher."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create an ir.sequence (required fields on hospitality.property)
        def _make_seq(name):
            return cls.env['ir.sequence'].create({
                'name': name,
                'code': name.lower().replace(' ', '_'),
                'prefix': name[:3].upper() + '/%(year)s/',
                'padding': 5,
            })

        # Two test properties
        cls.prop_a = cls.env['hospitality.property'].create({
            'name': 'Hotel Alpha',
            'code': 'ALPHA',
            'property_type': 'hotel',
            'timezone': 'UTC',
            'currency_id': cls.env.company.currency_id.id,
            'sequence_reservation_id': _make_seq('Reservation Alpha').id,
            'sequence_folio_id': _make_seq('Folio Alpha').id,
        })
        cls.prop_b = cls.env['hospitality.property'].create({
            'name': 'Resort Beta',
            'code': 'BETA',
            'property_type': 'resort',
            'timezone': 'UTC',
            'currency_id': cls.env.company.currency_id.id,
            'sequence_reservation_id': _make_seq('Reservation Beta').id,
            'sequence_folio_id': _make_seq('Folio Beta').id,
        })

        # Test user (no portal, plain internal)
        cls.test_user = cls.env['res.users'].create({
            'name': 'Hospitality Tester',
            'login': 'hosp_tester@test.com',
            'group_ids': [(4, cls.env.ref(
                'hospitality_base.group_hospitality_user').id)],
        })

    # ------------------------------------------------------------------
    # Test 1 — property_id defaults to first of property_ids
    # ------------------------------------------------------------------
    def test_01_default_property_is_first(self):
        """Assigning two properties sets current to the first one."""
        self.test_user.write({
            'property_ids': [(6, 0, [self.prop_a.id, self.prop_b.id])],
        })
        self.assertEqual(
            self.test_user.property_id, self.prop_a,
            "property_id should default to the first allowed property.",
        )

    # ------------------------------------------------------------------
    # Test 2 — removing current property resets to next available
    # ------------------------------------------------------------------
    def test_02_remove_current_resets_property(self):
        """When the current property is removed from the M2m, it resets."""
        self.test_user.write({
            'property_ids': [(6, 0, [self.prop_a.id, self.prop_b.id])],
            'property_id': self.prop_a.id,
        })
        # Remove prop_a from allowed list
        self.test_user.write({
            'property_ids': [(6, 0, [self.prop_b.id])],
        })
        self.assertEqual(
            self.test_user.property_id, self.prop_b,
            "property_id should reset to prop_b after prop_a is removed.",
        )

    # ------------------------------------------------------------------
    # Test 3 — constraint blocks setting a property not in allowed list
    # ------------------------------------------------------------------
    def test_03_constraint_blocks_disallowed_property(self):
        """Setting property_id to a property outside property_ids raises."""
        self.test_user.write({
            'property_ids': [(6, 0, [self.prop_a.id])],
        })
        with self.assertRaises(ValidationError):
            self.test_user.write({'property_id': self.prop_b.id})

    # ------------------------------------------------------------------
    # Test 4 — _get_property_context returns correct dict
    # ------------------------------------------------------------------
    def test_04_get_property_context(self):
        """_get_property_context returns default_property_id correctly."""
        self.test_user.write({
            'property_ids': [(6, 0, [self.prop_a.id])],
        })
        ctx = self.test_user._get_property_context()
        self.assertEqual(
            ctx, {'default_property_id': self.prop_a.id},
            "_get_property_context should return the current property id.",
        )

    # ------------------------------------------------------------------
    # Test 5 — res.company.property_ids reflects linked properties
    # ------------------------------------------------------------------
    def test_05_company_property_ids(self):
        """Company.property_ids returns all properties for that company."""
        company = self.env.company
        prop_ids = self.env['hospitality.property'].search(
            [('company_id', '=', company.id)]
        )
        self.assertEqual(
            set(company.property_ids.ids),
            set(prop_ids.ids),
            "company.property_ids must match properties with that company_id.",
        )