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
class TestMaintenanceSecurityGroups(TransactionCase):
    """MAINT-01: install sanity + security group scaffolding checks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref(
            'hospitality_maintenance.group_maintenance_user')
        cls.group_supervisor = cls.env.ref(
            'hospitality_maintenance.group_maintenance_supervisor')
        cls.group_admin = cls.env.ref(
            'hospitality_maintenance.group_maintenance_admin')

    def test_module_installed(self):
        """The module should be in the 'installed' state after setup."""
        module = self.env['ir.module.module'].search(
            [('name', '=', 'hospitality_maintenance')], limit=1)
        self.assertTrue(module, "hospitality_maintenance module record not found")
        self.assertEqual(module.state, 'installed')

    def test_three_groups_exist_with_no_category(self):
        """All three maintenance groups must exist with no privilege/
        category set — they should render as plain checkboxes under
        "Extra Rights" in Settings > Users, matching the convention used
        by hospitality_property, hospitality_folio, hospitality_front_desk
        and hospitality_housekeeping. They must also NOT imply
        base.group_user directly, since that group carries its own
        category (User Types) and would pull this chain out of the
        plain-checkbox "Extra Rights" section."""
        base_user = self.env.ref('base.group_user')
        for group in (self.group_user, self.group_supervisor, self.group_admin):
            self.assertTrue(group.exists())
            self.assertFalse(group.privilege_id)
            self.assertNotIn(base_user, group.implied_ids)

    def test_group_hierarchy_implied_ids(self):
        """Admin implies Supervisor implies User (internal chain only)."""
        self.assertIn(self.group_user, self.group_supervisor.implied_ids)
        self.assertIn(self.group_supervisor, self.group_admin.implied_ids)
        self.assertIn(self.group_user, self.group_admin.all_implied_ids)

    def test_admin_user_has_all_lower_groups(self):
        """A user in the admin group transitively has supervisor + user
        rights, provided they are already an internal user via Role."""
        admin_user = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Maintenance Admin Test User',
                'login': 'maint_admin_test_user',
                'email': 'maint_admin_test_user@example.com',
                'group_ids': [(6, 0, [
                    self.env.ref('base.group_user').id,
                    self.group_admin.id,
                ])],
            })
        self.assertTrue(admin_user.has_group(
            'hospitality_maintenance.group_maintenance_admin'))
        self.assertTrue(admin_user.has_group(
            'hospitality_maintenance.group_maintenance_supervisor'))
        self.assertTrue(admin_user.has_group(
            'hospitality_maintenance.group_maintenance_user'))