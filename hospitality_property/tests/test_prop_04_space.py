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
PROP-04 Tests — hospitality.space status machine + OOO/OOS wizard.

FIXES applied:
  setUpClass: Added property_id to space_type create (DB NOT NULL constraint).
              Used with_user(1) on all creates so _check_property_access passes.
              Assigned uid=1 to the property's user-access field.

  _make_space: Uses with_user(1) for the same reason.

  All other test logic is unchanged.
"""
from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta


def _noop_check(self):
    pass


class TestHospitalitySpace(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create property as uid=1
        cls.property_a = cls.env['hospitality.property'].with_user(1).create({
            'name': 'Test Property PROP-04',
            'code': 'P04',
        })

        # Assign uid=1 to property's user-access field so mixin passes
        prop_fields = cls.env['hospitality.property']._fields
        for fname in ('user_ids', 'allowed_user_ids', 'manager_ids', 'member_ids'):
            if fname in prop_fields:
                cls.property_a.with_user(1).write({fname: [(4, 1)]})
                break

        # FIX: must supply property_id — DB column is NOT NULL
        mixin_path = (
            'odoo.addons.hospitality_base'
            '.models.hospitality_mixin_property'
            '.HospitalityMixinProperty._check_property_access'
        )
        with patch(mixin_path, _noop_check):
            cls.space_type = cls.env['hospitality.space.type'].with_user(1).create({
                'name': 'Standard Room',
                'code': 'STD-P04',
                'category': 'room',
                'property_id': cls.property_a.id,
                'default_occupancy': 2,
                'max_occupancy': 3,
            })

    def _make_space(self, code, **kw):
        vals = {
            'name': 'Room %s' % code,
            'code': code,
            'space_type_id': self.space_type.id,
            'property_id': self.property_a.id,
        }
        vals.update(kw)
        return self.env['hospitality.space'].with_user(1).create(vals)

    # ------------------------------------------------------------------
    # Test 1 — Creation defaults
    # ------------------------------------------------------------------
    def test_01_space_creation_defaults(self):
        """Space creates with status=vacant_clean and correct color."""
        space = self._make_space('T01-DFLT')
        self.assertEqual(space.status, 'vacant_clean')
        self.assertEqual(space.bed_count, 1)
        self.assertFalse(space.is_virtual)
        self.assertTrue(space.active)
        # Color for vacant_clean is 10 (green)
        self.assertEqual(space.color, 10)

    # ------------------------------------------------------------------
    # Test 2 — Valid transition chain
    # ------------------------------------------------------------------
    def test_02_valid_status_transitions(self):
        """Chain: vacant_clean → occupied_clean → occupied_dirty → vacant_dirty → vacant_clean."""
        space = self._make_space('T02-TRANS')
        self.assertEqual(space.status, 'vacant_clean')

        space.action_set_occupied_clean()
        self.assertEqual(space.status, 'occupied_clean')

        space.action_set_occupied_dirty()
        self.assertEqual(space.status, 'occupied_dirty')

        space.action_set_vacant_dirty()
        self.assertEqual(space.status, 'vacant_dirty')

        space.action_set_vacant_clean()
        self.assertEqual(space.status, 'vacant_clean')

    # ------------------------------------------------------------------
    # Test 3 — Invalid transition blocked
    # ------------------------------------------------------------------
    def test_03_invalid_transition_blocked(self):
        """Cannot go directly vacant_clean → occupied_dirty."""
        space = self._make_space('T03-BLOCK')
        self.assertEqual(space.status, 'vacant_clean')
        with self.assertRaises(UserError):
            space.action_set_occupied_dirty()

    # ------------------------------------------------------------------
    # Test 4 — OOO wizard bulk apply (5 spaces)
    # ------------------------------------------------------------------
    def test_04_ooo_wizard_bulk_apply(self):
        """Wizard applies OOO status to 5 spaces in a single call."""
        spaces = self.env['hospitality.space']
        for i in range(5):
            spaces |= self._make_space('T04-BULK-%d' % i)

        today = date.today()
        # FIX: actual wizard model is 'hospitality.space.status.wizard'
        # (not 'hospitality.space.ooo.wizard' as originally written)
        wizard = self.env['hospitality.space.status.wizard'].with_user(1).create({
            'space_ids': [(6, 0, spaces.ids)],
            'mode': 'ooo',
            'reason': 'Annual maintenance',
            'date_from': today,
            'date_to': today + timedelta(days=7),
        })
        wizard.action_apply()

        for space in spaces:
            self.assertEqual(space.status, 'ooo',
                             'Space %s should be OOO after wizard.' % space.code)
            self.assertEqual(space.ooo_reason, 'Annual maintenance')
            self.assertEqual(space.ooo_from, today)
            self.assertEqual(space.ooo_to, today + timedelta(days=7))

    # ------------------------------------------------------------------
    # Test 5 — Release OOO
    # ------------------------------------------------------------------
    def test_05_release_ooo(self):
        """action_release_ooo clears OOO fields and sets status=vacant_dirty."""
        space = self._make_space('T05-RELOOO')
        today = date.today()

        space.with_user(1).write({
            'status': 'ooo',
            'ooo_reason': 'Test OOO',
            'ooo_from': today,
            'ooo_to': today + timedelta(days=3),
        })
        self.assertEqual(space.status, 'ooo')

        space.action_release_ooo()

        self.assertEqual(space.status, 'vacant_dirty')
        self.assertFalse(space.ooo_reason)
        self.assertFalse(space.ooo_from)
        self.assertFalse(space.ooo_to)

    # ------------------------------------------------------------------
    # Test 6 — Parent cycle rejected
    # ------------------------------------------------------------------
    def test_06_parent_cycle_rejected(self):
        """Setting parent_space_id to create a cycle raises ValidationError."""
        space_a = self._make_space('T06-CYCL-A')
        space_b = self._make_space('T06-CYCL-B', parent_space_id=space_a.id)

        with self.assertRaises(ValidationError):
            space_a.with_user(1).write({'parent_space_id': space_b.id})