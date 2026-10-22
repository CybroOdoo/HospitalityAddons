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
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestReportingGroups(TransactionCase):
    """REP-01: verify group_reporting_user / group_reporting_manager exist
    and imply the correct base hospitality groups."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_reporting_user = cls.env.ref(
            'hospitality_reporting.group_reporting_user')
        cls.group_reporting_manager = cls.env.ref(
            'hospitality_reporting.group_reporting_manager')
        cls.group_hospitality_user = cls.env.ref(
            'hospitality_base.group_hospitality_user')
        cls.group_hospitality_manager = cls.env.ref(
            'hospitality_base.group_hospitality_manager')

    def test_groups_exist(self):
        self.assertTrue(self.group_reporting_user.id)
        self.assertTrue(self.group_reporting_manager.id)

    def test_reporting_user_implies_hospitality_user(self):
        self.assertIn(
            self.group_hospitality_user,
            self.group_reporting_user.implied_ids,
            "Reporting User must imply hospitality_base.group_hospitality_user")

    def test_reporting_manager_implies_reporting_user_and_hospitality_manager(self):
        implied = self.group_reporting_manager.implied_ids
        self.assertIn(
            self.group_reporting_user, implied,
            "Reporting Manager must imply Reporting User (dashboard access)")
        self.assertIn(
            self.group_hospitality_manager, implied,
            "Reporting Manager must imply hospitality_base.group_hospitality_manager")

    def test_reporting_manager_full_chain_via_has_group(self):
        """A user in group_reporting_manager should transitively hold
        group_reporting_user and both base hospitality groups."""
        user = self.env['res.users'].create({
            'name': "Reporting Manager Test User",
            'login': "reporting_manager_test_user",
            'email': "reporting_manager_test_user@example.com",
            'group_ids': [(4, self.group_reporting_manager.id)],
        })
        self.assertTrue(
            user.has_group('hospitality_reporting.group_reporting_manager'))
        self.assertTrue(
            user.has_group('hospitality_reporting.group_reporting_user'),
            "Manager should transitively hold Reporting User via implied_ids")
        self.assertTrue(
            user.has_group('hospitality_base.group_hospitality_user'),
            "Manager should transitively hold the base hospitality user group")
        self.assertTrue(
            user.has_group('hospitality_base.group_hospitality_manager'))

    def test_reporting_user_does_not_grant_manager(self):
        """A plain Reporting User must NOT inherit manager-level access."""
        user = self.env['res.users'].create({
            'name': "Reporting User Test User",
            'login': "reporting_user_test_user",
            'email': "reporting_user_test_user@example.com",
            'group_ids': [(4, self.group_reporting_user.id)],
        })
        self.assertTrue(
            user.has_group('hospitality_reporting.group_reporting_user'))
        self.assertFalse(
            user.has_group('hospitality_reporting.group_reporting_manager'),
            "Reporting User must not implicitly hold Reporting Manager")