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
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHkDndLifecycle(TransactionCase):
    """Covers hospitality.dnd.entry: creation, clearing, and the
    search filter used by the DND menu to show only active entries.

    NOTE: property/space fixtures use only a minimal field set
    (name/code). Adjust setUpClass if hospitality.property or
    hospitality.space carry other required fields in this database.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DndEntry = cls.env['hospitality.dnd.entry']

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'HK DND Test Property',
                'code': 'HKDNDTEST',
            })

        cls.space_type = cls.env['hospitality.space.type'].search(
            [], limit=1)
        if not cls.space_type:
            cls.space_type = cls.env['hospitality.space.type'].create({
                'name': 'HK DND Test Type',
            })

        cls.space = cls.env['hospitality.space'].create({
            'name': 'HK DND Test Space',
            'code': 'HKDND1',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })

    def test_dnd_entry_created_active(self):
        """A new DND entry starts uncleared and is picked up by the
        'Active' search filter."""
        entry = self.DndEntry.create({
            'space_id': self.space.id,
            'reason': 'Guest sleeping',
        })
        self.assertFalse(entry.cleared_at)
        self.assertFalse(entry.cleared_by)

        active_entries = self.DndEntry.search(
            [('cleared_at', '=', False)])
        self.assertIn(entry, active_entries)

    def test_dnd_lifecycle(self):
        """Clearing a DND entry stamps cleared_at/cleared_by, and it
        drops out of the 'Active' filter."""
        entry = self.DndEntry.create({
            'space_id': self.space.id,
            'reason': 'Do not disturb sign on door',
        })
        entry.action_clear()

        self.assertTrue(entry.cleared_at)
        self.assertEqual(entry.cleared_by.id, self.env.uid)

        active_entries = self.DndEntry.search(
            [('cleared_at', '=', False)])
        self.assertNotIn(entry, active_entries)

        cleared_entries = self.DndEntry.search(
            [('cleared_at', '!=', False)])
        self.assertIn(entry, cleared_entries)

    def test_clearing_already_cleared_entry_raises(self):
        """Clearing an already-cleared entry raises rather than
        silently overwriting the original clear timestamp."""
        entry = self.DndEntry.create({'space_id': self.space.id})
        entry.action_clear()
        with self.assertRaises(UserError):
            entry.action_clear()