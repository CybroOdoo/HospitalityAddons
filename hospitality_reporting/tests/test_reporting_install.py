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
class TestReportingInstall(TransactionCase):
    """REP-01: verify the module installs cleanly and registers its
    security groups and placeholder menus."""

    def test_module_installed(self):
        module = self.env['ir.module.module'].search(
            [('name', '=', 'hospitality_reporting')], limit=1)
        self.assertTrue(module, "hospitality_reporting module record not found")
        self.assertEqual(
            module.state, 'installed',
            "hospitality_reporting should be in 'installed' state")

    def test_placeholder_submenus_exist(self):
        dashboards = self.env.ref(
            'hospitality_reporting.menu_hospitality_reporting_dashboards',
            raise_if_not_found=False)
        exports = self.env.ref(
            'hospitality_reporting.menu_hospitality_reporting_exports',
            raise_if_not_found=False)
        self.assertTrue(dashboards, "Dashboards placeholder menu missing")
        self.assertTrue(exports, "Exports placeholder menu missing")

    def test_reporting_menus_not_a_standalone_app(self):
        """Dashboards/Exports must NOT be root-level menus
        (parent_id=False is what makes something render as its own
        app) — both must be nested under the Hospitality app via the
        'parent' attribute in reporting_menus.xml."""
        dashboards = self.env.ref(
            'hospitality_reporting.menu_hospitality_reporting_dashboards')
        exports = self.env.ref(
            'hospitality_reporting.menu_hospitality_reporting_exports')
        self.assertTrue(
            dashboards.parent_id,
            "Dashboards menu has no parent — it will render as its own "
            "top-level app instead of living inside Hospitality.")
        self.assertTrue(
            exports.parent_id,
            "Exports menu has no parent — it will render as its own "
            "top-level app instead of living inside Hospitality.")
        app_root = dashboards.parent_id
        while app_root.parent_id:
            app_root = app_root.parent_id
        self.assertEqual(app_root.name, "Hospitality")