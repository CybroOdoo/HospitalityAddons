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
from odoo.tests.common import TransactionCase


class TestInstallAndGroupsVisible(TransactionCase):

    def test_groups_exist(self):
        agent_group = self.env.ref(
            'hospitality_front_desk.group_front_desk_agent', raise_if_not_found=False
        )
        supervisor_group = self.env.ref(
            'hospitality_front_desk.group_front_desk_supervisor', raise_if_not_found=False
        )
        self.assertIsNotNone(agent_group, "group_front_desk_agent not found")
        self.assertIsNotNone(supervisor_group, "group_front_desk_supervisor not found")

    def test_supervisor_implies_agent(self):
        supervisor = self.env.ref('hospitality_front_desk.group_front_desk_supervisor')
        agent = self.env.ref('hospitality_front_desk.group_front_desk_agent')
        self.assertIn(agent, supervisor.implied_ids, "Supervisor should imply Agent")
