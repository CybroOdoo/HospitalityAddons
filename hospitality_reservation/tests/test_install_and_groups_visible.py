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
# Copyright (C) 2024-Today Cybrosys Technologies(<https://www.cybrosys.com>).
# Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
# See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestInstallAndGroupsVisible(TransactionCase):
    """RES-01 acceptance test — two reservation groups must exist after install."""

    def test_group_reservation_agent_exists(self):
        """group_reservation_agent must be present in the database."""
        group = self.env.ref(
            'hospitality_reservation.group_reservation_agent',
            raise_if_not_found=False,
        )
        self.assertIsNotNone(
            group,
            "Expected 'group_reservation_agent' to exist after module install.",
        )
        self.assertEqual(group.name, 'Reservation Agent')

    def test_group_reservation_supervisor_exists(self):
        """group_reservation_supervisor must be present in the database."""
        group = self.env.ref(
            'hospitality_reservation.group_reservation_supervisor',
            raise_if_not_found=False,
        )
        self.assertIsNotNone(
            group,
            "Expected 'group_reservation_supervisor' to exist after module install.",
        )
        self.assertEqual(group.name, 'Reservation Supervisor')

    def test_supervisor_implies_agent(self):
        """Supervisor group must imply (inherit) the Agent group."""
        agent = self.env.ref('hospitality_reservation.group_reservation_agent')
        supervisor = self.env.ref(
            'hospitality_reservation.group_reservation_supervisor'
        )
        self.assertIn(
            agent,
            supervisor.implied_ids,
            "Supervisor group must have Agent in its implied_ids.",
        )

    def test_two_groups_total(self):
        """Exactly two reservation groups must be present (agent + supervisor)."""
        agent = self.env.ref('hospitality_reservation.group_reservation_agent')
        supervisor = self.env.ref(
            'hospitality_reservation.group_reservation_supervisor'
        )
        # Both records exist and are distinct
        self.assertNotEqual(agent.id, supervisor.id)