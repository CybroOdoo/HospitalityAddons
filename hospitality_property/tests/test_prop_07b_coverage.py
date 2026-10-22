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
PROP-07 Tests (Part B) — Coverage completeness.

Covers paths not exercised by PROP-02 through PROP-05 to push
module coverage toward ≥ 85 %.

Test cases:
  1.  test_01_inspected_transition     — vacant_clean → inspected.
  2.  test_02_pickup_transition        — vacant_dirty → pickup.
  3.  test_03_release_oos              — action_release_oos clears OOS.
  4.  test_04_oos_wizard               — wizard applies OOS to 3 spaces.
  5.  test_05_ooo_date_validation      — ooo_to < ooo_from raises ValidationError.
  6.  test_06_oos_date_validation      — oos_to < oos_from raises ValidationError.
  7.  test_07_space_type_code_uniq     — duplicate code per property rejected.
  8.  test_08_floor_code_uniq_per_bldg — duplicate floor code per building rejected.
  9.  test_09_space_code_uniq          — duplicate space code per property rejected.
  10. test_10_section_property_related — section.property_id mirrors building.
"""
from datetime import date, timedelta
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


def _noop_check(self):
    pass


MIXIN_PATH = (
    'odoo.addons.hospitality_base'
    '.models.hospitality_mixin_property'
    '.HospitalityMixinProperty._check_property_access'
)


class TestProp07Coverage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.prop = cls.env['hospitality.property'].with_user(1).create({
            'name': 'Coverage Property P07',
            'code': 'P07C',
        })
        prop_fields = cls.env['hospitality.property']._fields
        for fname in ('user_ids', 'allowed_user_ids', 'manager_ids', 'member_ids'):
            if fname in prop_fields:
                cls.prop.with_user(1).write({fname: [(4, 1)]})
                break

        with patch(MIXIN_PATH, _noop_check):
            cls.stype = cls.env['hospitality.space.type'].with_user(1).create({
                'name': 'Standard P07',
                'code': 'STD-P07C',
                'category': 'room',
                'property_id': cls.prop.id,
                'default_occupancy': 2,
                'max_occupancy': 3,
            })
            cls.building = cls.env['hospitality.building'].sudo().create({
                'name': 'Coverage Building',
                'code': 'COV-BLDG',
                'property_id': cls.prop.id,
            })
            cls.floor = cls.env['hospitality.floor'].sudo().create({
                'name': 'Coverage Floor',
                'code': 'COV-F1',
                'building_id': cls.building.id,
            })

    def _space(self, code, **kw):
        vals = {
            'name': 'Space %s' % code,
            'code': code,
            'space_type_id': self.stype.id,
            'property_id': self.prop.id,
        }
        vals.update(kw)
        return self.env['hospitality.space'].with_user(1).create(vals)

    # ------------------------------------------------------------------
    # 1. vacant_clean → inspected
    # ------------------------------------------------------------------
    def test_01_inspected_transition(self):
        """action_set_inspected sets status to inspected from vacant_clean."""
        s = self._space('P07-INSP')
        self.assertEqual(s.status, 'vacant_clean')
        s.action_set_inspected()
        self.assertEqual(s.status, 'inspected')

    # ------------------------------------------------------------------
    # 2. pickup transition
    # ------------------------------------------------------------------
    def test_02_pickup_transition(self):
        """action_set_pickup works from vacant_clean and vacant_dirty."""
        s = self._space('P07-PKUP')
        s.action_set_pickup()
        self.assertEqual(s.status, 'pickup')

        # vacant_dirty → pickup
        s2 = self._space('P07-PKUP2')
        s2.with_user(1).write({'status': 'vacant_dirty'})
        s2.action_set_pickup()
        self.assertEqual(s2.status, 'pickup')

    # ------------------------------------------------------------------
    # 3. release_oos
    # ------------------------------------------------------------------
    def test_03_release_oos(self):
        """action_release_oos clears OOS fields and sets vacant_dirty."""
        today = date.today()
        s = self._space('P07-ROOS')
        s.with_user(1).write({
            'status': 'oos',
            'oos_reason': 'Test OOS',
            'oos_from': today,
            'oos_to': today + timedelta(days=10),
        })
        s.action_release_oos()
        self.assertEqual(s.status, 'vacant_dirty')
        self.assertFalse(s.oos_reason)
        self.assertFalse(s.oos_from)
        self.assertFalse(s.oos_to)

    # ------------------------------------------------------------------
    # 4. OOS wizard bulk apply
    # ------------------------------------------------------------------
    def test_04_oos_wizard_bulk(self):
        """OOS wizard applies to 3 spaces in one call."""
        spaces = self.env['hospitality.space']
        for i in range(3):
            spaces |= self._space('P07-WZ-OOS-%d' % i)

        today = date.today()
        wizard = self.env['hospitality.space.status.wizard'].with_user(1).create({
            'space_ids': [(6, 0, spaces.ids)],
            'mode': 'oos',
            'reason': 'Plumbing works',
            'date_from': today,
            'date_to': today + timedelta(days=14),
        })
        wizard.action_apply()

        for sp in spaces:
            self.assertEqual(sp.status, 'oos')
            self.assertEqual(sp.oos_reason, 'Plumbing works')

    # ------------------------------------------------------------------
    # 5. OOO date validation — ooo_to < ooo_from
    # ------------------------------------------------------------------
    def test_05_ooo_date_validation(self):
        """ooo_to before ooo_from must raise ValidationError."""
        today = date.today()
        s = self._space('P07-OOODT')
        with self.assertRaises(ValidationError):
            s.with_user(1).write({
                'status': 'ooo',
                'ooo_reason': 'Bad dates',
                'ooo_from': today + timedelta(days=5),
                'ooo_to': today + timedelta(days=2),
            })

    # ------------------------------------------------------------------
    # 6. OOS date validation — oos_to < oos_from
    # ------------------------------------------------------------------
    def test_06_oos_date_validation(self):
        """oos_to before oos_from must raise ValidationError."""
        today = date.today()
        s = self._space('P07-OOSDT')
        with self.assertRaises(ValidationError):
            s.with_user(1).write({
                'status': 'oos',
                'oos_reason': 'Bad dates',
                'oos_from': today + timedelta(days=10),
                'oos_to': today + timedelta(days=3),
            })

    # ------------------------------------------------------------------
    # 7. Space type code unique per property
    # ------------------------------------------------------------------
    def test_07_space_type_code_unique(self):
        """Duplicate space type code per property must raise ValidationError."""
        with patch(MIXIN_PATH, _noop_check):
            self.env['hospitality.space.type'].with_user(1).create({
                'name': 'Unique Type',
                'code': 'UNQ-P07',
                'category': 'room',
                'property_id': self.prop.id,
                'default_occupancy': 1,
                'max_occupancy': 2,
            })
        with patch(MIXIN_PATH, _noop_check):
            with self.assertRaises(ValidationError):
                self.env['hospitality.space.type'].with_user(1).create({
                    'name': 'Duplicate Type',
                    'code': 'UNQ-P07',
                    'category': 'suite',
                    'property_id': self.prop.id,
                    'default_occupancy': 1,
                    'max_occupancy': 2,
                })

    # ------------------------------------------------------------------
    # 8. Floor code unique per building
    # ------------------------------------------------------------------
    def test_08_floor_code_unique_per_building(self):
        """Duplicate floor code under same building must be rejected."""
        self.env['hospitality.floor'].sudo().create({
            'name': 'Level X',
            'code': 'LVL-X',
            'building_id': self.building.id,
        })
        with self.assertRaises(Exception):
            self.env['hospitality.floor'].sudo().create({
                'name': 'Level X Dup',
                'code': 'LVL-X',
                'building_id': self.building.id,
            })

    # ------------------------------------------------------------------
    # 9. Space code unique per property
    # ------------------------------------------------------------------
    def test_09_space_code_unique_per_property(self):
        """Duplicate space code under same property must be rejected."""
        self._space('DUPSP-P07')
        with self.assertRaises(Exception):
            self._space('DUPSP-P07')

    # ------------------------------------------------------------------
    # 10. Section property_id inherits from building
    # ------------------------------------------------------------------
    def test_10_section_property_related(self):
        """section.property_id must equal building.property_id."""
        section = self.env['hospitality.section'].sudo().create({
            'name': 'Coverage Section',
            'code': 'COV-SEC',
            'building_id': self.building.id,
        })
        self.assertEqual(
            section.property_id, self.prop,
            'Section property_id must be inherited from its building.',
        )