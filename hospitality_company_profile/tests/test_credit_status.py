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
from odoo.tests import tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install')
class TestCreditStatus(TransactionCase):
    """COMP-04 acceptance tests — credit limit / used / status thresholds + cron."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.Move = cls.env['account.move']

        cls.partner = cls.Partner.create({
            'name': 'Credit Test Partner',
            'is_corporate_account': True,
            'hospitality_credit_limit': 1000.0,
        })

    # ── helpers ───────────────────────────────────────────────────────────────

    def _create_open_invoice(self, amount, partner=None):
        """Create and post a customer invoice with the given amount, unpaid."""
        partner = partner or self.partner
        move = self.Move.create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Test Line',
                'quantity': 1,
                'price_unit': amount,
            })],
        })
        move.action_post()
        return move

    def _refresh_credit(self, partner=None):
        """Force recompute of credit_used/credit_status (mimics cron behaviour).

        credit_used is store=True but its @api.depends only lists the
        corporate/TA/OTA boolean flags — invoice changes do NOT trigger an
        automatic recompute.  We must call _compute_* explicitly, exactly as
        the production cron does.
        """
        p = partner or self.partner
        p._compute_credit_used()
        p._compute_credit_status()

    @staticmethod
    def _add_user_to_group(user, group):
        """Assign a user to a group — Odoo 19 compatible.

        'groups_id' on res.users and 'users' on res.groups were both removed
        in Odoo 19.  The supported path is writing 'group_ids' on the user.
        """
        user.sudo().write({'group_ids': [(4, group.id)]})

    @staticmethod
    def _remove_user_from_group(user, group):
        user.sudo().write({'group_ids': [(3, group.id)]})

    # ── test_ok_when_below_80pct ──────────────────────────────────────────────

    def test_ok_when_below_80pct(self):
        """credit_used at 50% of limit -> status 'ok'."""
        self._create_open_invoice(500.0)
        self._refresh_credit()
        self.assertAlmostEqual(self.partner.credit_used, 500.0, places=2)
        self.assertEqual(self.partner.credit_status, 'ok')

    # ── test_near_limit_at_85pct ──────────────────────────────────────────────

    def test_near_limit_at_85pct(self):
        """credit_used at 85% of limit -> status 'near_limit'."""
        self._create_open_invoice(850.0)
        self._refresh_credit()
        self.assertAlmostEqual(self.partner.credit_used, 850.0, places=2)
        self.assertEqual(self.partner.credit_status, 'near_limit')

    # ── test_exceeded_above_100pct ────────────────────────────────────────────

    def test_exceeded_above_100pct(self):
        """credit_used above limit -> status 'exceeded'."""
        self._create_open_invoice(1200.0)
        self._refresh_credit()
        self.assertAlmostEqual(self.partner.credit_used, 1200.0, places=2)
        self.assertEqual(self.partner.credit_status, 'exceeded')

    # ── test_manual_hold_overrides_ok ─────────────────────────────────────────

    def test_manual_hold_overrides_ok(self):
        """credit_hold_manual=True forces 'on_hold' even with credit_used=0."""
        partner = self.Partner.create({
            'name': 'Manual Hold Partner',
            'is_corporate_account': True,
            'hospitality_credit_limit': 1000.0,
        })
        partner.sudo().write({'credit_hold_manual': True})
        partner._compute_credit_status()
        self.assertEqual(partner.credit_status, 'on_hold')

    def test_zero_limit_is_ok(self):
        """hospitality_credit_limit=0 -> status 'ok' regardless of credit_used."""
        partner = self.Partner.create({
            'name': 'No Limit Partner',
            'is_corporate_account': True,
            'hospitality_credit_limit': 0.0,
        })
        partner._compute_credit_status()
        self.assertEqual(partner.credit_status, 'ok')

    # ── test_finance_only_can_set_limit ───────────────────────────────────────

    def test_finance_only_can_set_limit(self):
        """A user without group_corporate_finance cannot write hospitality_credit_limit."""
        manager_group = self.env.ref('hospitality_company_profile.group_corporate_manager')
        user_group = self.env.ref('hospitality_company_profile.group_corporate_user')
        finance_group = self.env.ref('hospitality_company_profile.group_corporate_finance')

        non_finance_user = self.env['res.users'].create({
            'name': 'Non Finance User',
            'login': 'non_finance_user_comp04@example.com',
        })
        self._add_user_to_group(non_finance_user, self.env.ref('base.group_user'))
        self._add_user_to_group(non_finance_user, self.env.ref('base.group_partner_manager'))
        self._add_user_to_group(non_finance_user, user_group)
        self._add_user_to_group(non_finance_user, manager_group)
        self._remove_user_from_group(non_finance_user, finance_group)

        partner_as_other_user = self.partner.with_user(non_finance_user)
        with self.assertRaises(AccessError, msg=(
            "User without group_corporate_finance must not be able to "
            "write hospitality_credit_limit."
        )):
            partner_as_other_user.write({'hospitality_credit_limit': 5000.0})

    def test_finance_user_can_set_limit(self):
        """A user with group_corporate_finance CAN write hospitality_credit_limit."""
        finance_group = self.env.ref('hospitality_company_profile.group_corporate_finance')
        user_group = self.env.ref('hospitality_company_profile.group_corporate_user')

        finance_user = self.env['res.users'].create({
            'name': 'Finance User',
            'login': 'finance_user_comp04@example.com',
        })
        self._add_user_to_group(finance_user, self.env.ref('base.group_user'))
        # FIX: finance user also needs Contact/Creation (group_partner_manager)
        # to be allowed to write res.partner records at all
        self._add_user_to_group(finance_user, self.env.ref('base.group_partner_manager'))
        self._add_user_to_group(finance_user, user_group)
        self._add_user_to_group(finance_user, finance_group)

        partner_as_finance = self.partner.with_user(finance_user)
        partner_as_finance.write({'hospitality_credit_limit': 2500.0})
        self.assertEqual(self.partner.hospitality_credit_limit, 2500.0)

    # ── test_cron_refreshes_credit_used ───────────────────────────────────────

    def test_cron_refreshes_credit_used(self):
        """_cron_credit_recompute updates credit_used for corporate/TA/OTA partners."""
        partner = self.Partner.create({
            'name': 'Cron Test Partner',
            'is_corporate_account': True,
            'hospitality_credit_limit': 1000.0,
        })
        partner._compute_credit_used()
        self.assertAlmostEqual(partner.credit_used, 0.0, places=2)
        self.assertEqual(partner.credit_status, 'ok')

        self._create_open_invoice(900.0, partner=partner)

        self.Partner._cron_credit_recompute()

        partner.invalidate_recordset(['credit_used', 'credit_status'])
        self.assertAlmostEqual(partner.credit_used, 900.0, places=2,
            msg="Cron should refresh credit_used to reflect the new open invoice.")
        self.assertEqual(partner.credit_status, 'near_limit',
            msg="900/1000 = 90% should be near_limit after cron refresh.")