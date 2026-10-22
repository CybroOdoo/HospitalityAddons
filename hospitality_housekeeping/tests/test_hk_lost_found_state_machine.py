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
class TestHkLostFoundStateMachine(TransactionCase):
    """Covers hospitality.lost.found: logged -> stored -> returned /
    donated / disposed, and that invalid transitions are rejected.

    NOTE: property/space fixtures use only a minimal field set
    (name/code). Adjust setUpClass if hospitality.property or
    hospitality.space carry other required fields in this database.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.LostFound = cls.env['hospitality.lost.found']

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'HK Lost Found Test Property',
                'code': 'HKLFTEST',
            })

        cls.space_type = cls.env['hospitality.space.type'].search(
            [], limit=1)
        if not cls.space_type:
            cls.space_type = cls.env['hospitality.space.type'].create({
                'name': 'HK Lost Found Test Type',
            })

        cls.space = cls.env['hospitality.space'].create({
            'name': 'HK Lost Found Test Space',
            'code': 'HKLF1',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })

        cls.owner = cls.env['res.partner'].create({
            'name': 'HK Lost Found Test Owner',
        })

    def _create_item(self):
        return self.LostFound.create({
            'property_id': self.property.id,
            'found_in_space_id': self.space.id,
            'description': 'Blue umbrella left in the room',
        })

    def test_lost_found_state_machine(self):
        """Acceptance path: logged -> stored -> returned, recorded
        with timestamps via mail.thread tracking on the state field."""
        item = self._create_item()
        self.assertEqual(item.state, 'logged')

        item.action_store(storage_location='Front Desk Safe')
        self.assertEqual(item.state, 'stored')
        self.assertEqual(item.storage_location, 'Front Desk Safe')

        item.action_return(owner_partner_id=self.owner.id)
        self.assertEqual(item.state, 'returned')
        self.assertEqual(item.owner_partner_id, self.owner)

        # Every transition is logged on the chatter explicitly by
        # write(), giving a timestamped audit trail of
        # logged -> stored -> returned.
        status_messages = item.message_ids.filtered(
            lambda m: m.body and 'Status changed' in m.body)
        self.assertGreaterEqual(len(status_messages), 2)

    def test_donate_path(self):
        """stored -> donated when never claimed."""
        item = self._create_item()
        item.action_store()
        item.action_donate()
        self.assertEqual(item.state, 'donated')

    def test_dispose_path_from_logged_and_stored(self):
        """disposed is reachable directly from logged or from
        stored."""
        item_from_logged = self._create_item()
        item_from_logged.action_dispose()
        self.assertEqual(item_from_logged.state, 'disposed')

        item_from_stored = self._create_item()
        item_from_stored.action_store()
        item_from_stored.action_dispose()
        self.assertEqual(item_from_stored.state, 'disposed')

    def test_invalid_transitions_raise(self):
        """Skipping ahead in the state machine raises a UserError."""
        item = self._create_item()

        with self.assertRaises(UserError):
            item.action_return()

        with self.assertRaises(UserError):
            item.action_donate()

        item.action_store()

        with self.assertRaises(UserError):
            item.action_store()

        item.action_return()

        with self.assertRaises(UserError):
            item.action_dispose()