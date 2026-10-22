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
FOL-01 — Scaffolding + Security
Tests:
    * test_install_and_groups_visible

Convention (matches hospitality_property, hospitality_reservation,
hospitality_rate): groups have NO category_id and NO privilege_id.
They appear as plain checkboxes under Extra Rights on the user form.

Odoo 19 note: res.groups no longer has a category_id field at all —
accessing it raises AttributeError, so we do not test for its absence.
"""
from odoo.tests.common import TransactionCase


class TestFol01InstallAndGroups(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref("hospitality_folio.group_folio_user")
        cls.group_cashier = cls.env.ref("hospitality_folio.group_folio_cashier")
        cls.group_supervisor = cls.env.ref("hospitality_folio.group_folio_supervisor")

    # ------------------------------------------------------------------ #
    #  Existence                                                           #
    # ------------------------------------------------------------------ #

    def test_group_folio_user_exists(self):
        self.assertTrue(self.group_user, "group_folio_user missing after install.")

    def test_group_folio_cashier_exists(self):
        self.assertTrue(self.group_cashier, "group_folio_cashier missing after install.")

    def test_group_folio_supervisor_exists(self):
        self.assertTrue(self.group_supervisor, "group_folio_supervisor missing after install.")

    # ------------------------------------------------------------------ #
    #  No privilege (Extra Rights convention)                             #
    # ------------------------------------------------------------------ #

    def test_groups_have_no_privilege(self):
        """Groups must not be attached to any res.groups.privilege —
        matching the convention used by all other Business Kit modules."""
        for grp in (self.group_user, self.group_cashier, self.group_supervisor):
            privilege = getattr(grp, "privilege_id", None)
            if privilege is not None:
                self.assertFalse(
                    privilege,
                    f"{grp.name} should have no privilege_id (Extra Rights convention).",
                )

    # ------------------------------------------------------------------ #
    #  Inheritance chain                                                   #
    # ------------------------------------------------------------------ #

    def test_cashier_implies_user(self):
        self.assertIn(self.group_user, self.group_cashier.implied_ids)

    def test_supervisor_implies_cashier(self):
        self.assertIn(self.group_cashier, self.group_supervisor.implied_ids)

    def test_supervisor_transitively_implies_user(self):
        trans = getattr(self.group_supervisor, "trans_implied_ids", None)
        if trans is not None:
            self.assertIn(self.group_user, trans)
        else:
            self.assertIn(self.group_cashier, self.group_supervisor.implied_ids)
            self.assertIn(self.group_user, self.group_cashier.implied_ids)

    # ------------------------------------------------------------------ #
    #  Dependency smoke-tests                                              #
    # ------------------------------------------------------------------ #

    def _module_installed(self, name):
        return bool(self.env["ir.module.module"].search(
            [("name", "=", name), ("state", "=", "installed")], limit=1
        ))

    def test_hospitality_reservation_installed(self):
        self.assertTrue(self._module_installed("hospitality_reservation"))

    def test_account_installed(self):
        self.assertTrue(self._module_installed("account"))