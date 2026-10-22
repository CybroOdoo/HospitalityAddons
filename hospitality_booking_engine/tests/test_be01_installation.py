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
class TestBE01Installation(TransactionCase):
    """BE-01: install + security group sanity checks.

    security_groups.xml intentionally defines group_be_manager with no
    privilege_id / category — it renders under Users > Extra Rights,
    matching the Folio-style security setup elsewhere in the suite. These
    tests match that design; they do NOT assume a res.groups.privilege or
    ir.module.category exists for this module.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_be_manager = cls.env.ref(
            'hospitality_booking_engine.group_be_manager'
        )
        cls.group_public = cls.env.ref('base.group_public')

    def test_module_installed(self):
        module = self.env['ir.module.module'].search(
            [('name', '=', 'hospitality_booking_engine')]
        )
        self.assertTrue(module, "hospitality_booking_engine module not found.")
        self.assertEqual(
            module.state, 'installed',
            "hospitality_booking_engine should be installed for this test to run."
        )

    def test_group_be_manager_exists(self):
        self.assertTrue(self.group_be_manager.exists())
        self.assertEqual(self.group_be_manager.name, 'Booking Engine Manager')

    def test_group_be_manager_has_no_privilege(self):
        """Confirms the current (Extra Rights) design is intact. If a
        privilege/category is added back later, update this test rather
        than leaving it silently out of sync."""
        self.assertFalse(
            self.group_be_manager.privilege_id,
            "group_be_manager unexpectedly has a privilege_id set — "
            "if this was an intentional design change, update this test."
        )

    def test_group_be_manager_comment_set(self):
        self.assertTrue(
            (self.group_be_manager.comment or '').strip(),
            "group_be_manager should have a descriptive comment."
        )

    def test_no_duplicate_be_manager_group(self):
        """Guards against a second 'Booking Engine Manager'-named group
        being introduced by a future data file."""
        matches = self.env['res.groups'].search(
            [('name', '=', 'Booking Engine Manager')]
        )
        self.assertEqual(
            len(matches), 1,
            "Expected exactly one 'Booking Engine Manager' group, found %d."
            % len(matches)
        )

    def test_public_group_untouched(self):
        """Public/anonymous access rides on base.group_public — this
        module must not define its own public-facing group."""
        self.assertTrue(self.group_public.exists())
        stray = self.env['res.groups'].search([
            ('name', 'ilike', 'public'),
            ('id', '!=', self.group_public.id),
        ]).filtered(
            lambda g: 'booking_engine' in (g.get_external_id().get(g.id) or '')
        )
        self.assertFalse(
            stray,
            "Found an unexpected custom 'public' group defined by "
            "hospitality_booking_engine: %s" % stray.mapped('name')
        )