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
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCashierScaffolding(TransactionCase):
    """CASH-01: module install and security group sanity checks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref('base.user_admin'))

    def test_module_installed(self):
        """The module record itself should be in the 'installed' state."""
        module = self.env['ir.module.module'].with_user(1).search(
            [('name', '=', 'hospitality_cashiering')]
        )
        self.assertTrue(module, "hospitality_cashiering module record not found.")
        self.assertEqual(
            module.state, 'installed',
            "hospitality_cashiering should be installed."
        )

    def test_groups_exist(self):
        """Both cashier security groups should be created by the module."""
        cashier_group = self.env.ref(
            'hospitality_cashiering.group_cashier', raise_if_not_found=False
        )
        supervisor_group = self.env.ref(
            'hospitality_cashiering.group_cashier_supervisor',
            raise_if_not_found=False
        )
        self.assertTrue(cashier_group, "group_cashier was not created.")
        self.assertTrue(
            supervisor_group, "group_cashier_supervisor was not created."
        )

    def test_supervisor_implies_cashier(self):
        """Cashier Supervisor should inherit all Cashier rights."""
        cashier_group = self.env.ref('hospitality_cashiering.group_cashier')
        supervisor_group = self.env.ref(
            'hospitality_cashiering.group_cashier_supervisor'
        )
        self.assertIn(
            cashier_group, supervisor_group.implied_ids,
            "group_cashier_supervisor should imply group_cashier."
        )

    def test_menu_root_exists(self):
        """The Cashier Shifts menu should be created, mounted under the
        shared Operations menu, and restricted to the cashiering
        groups. (Renamed from a CASH-01 standalone root menu, which was
        replaced in CASH-02 by mounting under menu_hospitality_operations
        instead of a dedicated top-level app.)"""
        menu = self.env.ref('hospitality_cashiering.menu_cashier_shifts')
        cashier_group = self.env.ref('hospitality_cashiering.group_cashier')
        supervisor_group = self.env.ref(
            'hospitality_cashiering.group_cashier_supervisor'
        )
        self.assertTrue(menu.exists())
        self.assertIn(cashier_group, menu.group_ids)
        self.assertIn(supervisor_group, menu.group_ids)