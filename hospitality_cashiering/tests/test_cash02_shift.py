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
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCashierShift(TransactionCase):
    """CASH-02: shift lifecycle, multi-currency variance, and guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref('base.user_admin'))

        cls.currency_usd = cls.env.ref('base.USD')
        cls.currency_eur = cls.env.ref('base.EUR')
        if not cls.currency_eur.active:
            cls.currency_eur.active = True
        company = cls.env.company
        if cls.currency_eur != company.currency_id:
            existing_rate = cls.env['res.currency.rate'].search([
                ('currency_id', '=', cls.currency_eur.id),
                ('company_id', 'in', [company.id, False]),
            ], limit=1)
            if not existing_rate:
                cls.env['res.currency.rate'].create({
                    'currency_id': cls.currency_eur.id,
                    'company_id': company.id,
                    'rate': 0.9,
                    'name': fields.Date.context_today(cls.env['res.currency']),
                })

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'Test Property',
                'code': 'TST',
            })

        # Odoo 19: res.users field renamed groups_id -> group_ids
        cls.cashier_user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Test Cashier',
                'login': 'test_cash02_cashier',
                'email': 'test_cash02_cashier@example.com',
                'group_ids': [(6, 0, [
                    cls.env.ref('base.group_user').id,
                    cls.env.ref('hospitality_cashiering.group_cashier').id,
                ])],
            })
        cls.supervisor_user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Test Cashier Supervisor',
                'login': 'test_cash02_supervisor',
                'email': 'test_cash02_supervisor@example.com',
                'group_ids': [(6, 0, [
                    cls.env.ref('base.group_user').id,
                    cls.env.ref(
                        'hospitality_cashiering.group_cashier_supervisor').id,
                ])],
            })

    def _create_shift(self, user=None):
        return self.env['hospitality.cashier.shift'].create({
            'user_id': (user or self.cashier_user).id,
            'property_id': self.property.id,
        })

    def test_shift_lifecycle(self):
        """A shift is created open, gets a sequence-driven name, and can
        be closed once closing amounts are captured."""
        shift = self._create_shift()
        self.assertEqual(shift.state, 'open')
        self.assertNotEqual(shift.name, 'New')
        self.assertTrue(shift.name)

        self.env['hospitality.cashier.amount'].create({
            'shift_id': shift.id,
            'kind': 'closing',
            'currency_id': self.currency_usd.id,
            'amount': 100.0,
        })
        shift.action_close_shift()
        self.assertEqual(shift.state, 'closed')
        self.assertTrue(shift.ended_at)

    def test_variance_computation(self):
        """Variance must correctly net a multi-currency closing drawer
        against the expected total (0, since no folio payments are
        created in this test) in the shift's reporting currency."""
        shift = self._create_shift()
        company_currency = self.env.company.currency_id

        self.env['hospitality.cashier.amount'].create({
            'shift_id': shift.id,
            'kind': 'closing',
            'currency_id': company_currency.id,
            'amount': 150.0,
        })
        if self.currency_eur != company_currency:
            self.env['hospitality.cashier.amount'].create({
                'shift_id': shift.id,
                'kind': 'closing',
                'currency_id': self.currency_eur.id,
                'amount': 50.0,
            })

        shift.action_close_shift()

        # With no matching folio payment lines, expected_total is 0, so
        # variance should equal the converted closing total exactly.
        expected_closing_total = sum(
            line.currency_id._convert(
                line.amount, shift.currency_id, self.env.company,
                shift.ended_at.date())
            for line in shift.closing_amount_ids
        )
        self.assertAlmostEqual(
            shift.variance, expected_closing_total - shift.expected_total,
            places=2,
        )

    def test_close_requires_closing_amount(self):
        """A shift cannot be closed without at least one closing amount
        line captured."""
        shift = self._create_shift()
        with self.assertRaises(UserError):
            shift.action_close_shift()
        self.assertEqual(shift.state, 'open')

    def test_audit_supervisor_only(self):
        """Only a Cashier Supervisor can audit a closed shift."""
        shift = self._create_shift()
        self.env['hospitality.cashier.amount'].create({
            'shift_id': shift.id,
            'kind': 'closing',
            'currency_id': self.currency_usd.id,
            'amount': 100.0,
        })
        shift.action_close_shift()

        with self.assertRaises(AccessError):
            shift.with_user(self.cashier_user).action_audit()
        self.assertEqual(shift.state, 'closed')

        shift.with_user(self.supervisor_user).action_audit()
        self.assertEqual(shift.state, 'audited')