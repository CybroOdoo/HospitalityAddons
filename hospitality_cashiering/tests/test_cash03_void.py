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
class TestCashierVoidRequest(TransactionCase):
    """CASH-03: void approval workflow + shift closeout report."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref('base.user_admin'))

        cls.currency_usd = cls.env.ref('base.USD')

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'Test Property',
                'code': 'TST',
            })

        # Odoo 19: res.users field renamed groups_id -> group_ids
        cls.cashier_user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Test Void Cashier',
                'login': 'test_cash03_cashier',
                'email': 'test_cash03_cashier@example.com',
                'group_ids': [(6, 0, [
                    cls.env.ref('base.group_user').id,
                    cls.env.ref('hospitality_cashiering.group_cashier').id,
                ])],
            })
        cls.supervisor_user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Test Void Cashier Supervisor',
                'login': 'test_cash03_supervisor',
                'email': 'test_cash03_supervisor@example.com',
                'group_ids': [(6, 0, [
                    cls.env.ref('base.group_user').id,
                    cls.env.ref(
                        'hospitality_cashiering.group_cashier_supervisor').id,
                ])],
            })

        cls.partner = cls.env['res.partner'].create({'name': 'Test Guest'})

        cls.transaction_code = cls.env['hospitality.transaction.code'].search(
            [('transaction_type', '=', 'charge')], limit=1)
        if not cls.transaction_code:
            cls.transaction_code = cls.env['hospitality.transaction.code'].create({
                'name': 'Room Charge',
                'code': 'ROOM',
                'transaction_type': 'charge',
            })

        cls.folio = cls.env['hospitality.folio'].create({
            'property_id': cls.property.id,
            'partner_id': cls.partner.id,
            'currency_id': cls.currency_usd.id,
        })
        cls.folio.action_open_folio()

    def _create_folio_line(self):
        return self.env['hospitality.folio.line'].create({
            'folio_id': self.folio.id,
            'transaction_code_id': self.transaction_code.id,
            'qty': 1,
            'unit_price': 100.0,
        })

    def _create_void_request(self, line, user=None):
        return self.env['hospitality.void.request'].with_user(
            user or self.cashier_user).create({
                'folio_line_id': line.id,
                'reason': 'Guest disputed the charge.',
            })

    def test_void_request_approval_creates_mirror_line(self):
        """Approving a requested void executes _void_line(), creating a
        negative mirror line and moving the request to 'approved'."""
        line = self._create_folio_line()
        lines_before = self.folio.line_ids

        request = self._create_void_request(line)
        self.assertEqual(request.state, 'requested')

        request.with_user(self.supervisor_user).action_approve()

        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.approved_by, self.supervisor_user)
        self.assertTrue(request.approved_at)

        new_lines = self.folio.line_ids - lines_before
        self.assertEqual(len(new_lines), 1, "Exactly one mirror line should be created.")
        mirror_line = new_lines[0]
        self.assertTrue(mirror_line.is_void)
        self.assertEqual(mirror_line.void_of_id, line)
        self.assertAlmostEqual(mirror_line.qty, -line.qty)

    def test_void_request_rejection_keeps_line(self):
        """Rejecting a request leaves the original folio line untouched
        and creates no mirror line."""
        line = self._create_folio_line()
        lines_before = self.folio.line_ids
        original_qty = line.qty
        original_amount_total = line.amount_total

        request = self._create_void_request(line)
        request.with_user(self.supervisor_user).action_reject()

        self.assertEqual(request.state, 'rejected')
        self.assertEqual(request.approved_by, self.supervisor_user)

        self.assertEqual(line.qty, original_qty)
        self.assertEqual(line.amount_total, original_amount_total)
        self.assertFalse(line.is_void)
        self.assertEqual(self.folio.line_ids, lines_before,
                          "No mirror line should be created on rejection.")

    def test_void_request_approve_reject_supervisor_only(self):
        """A plain Cashier cannot approve or reject a void request."""
        line = self._create_folio_line()
        request = self._create_void_request(line)

        with self.assertRaises(AccessError):
            request.with_user(self.cashier_user).action_approve()

        with self.assertRaises(AccessError):
            request.with_user(self.cashier_user).action_reject()

        self.assertEqual(request.state, 'requested')

    def test_shift_closeout_pdf_renders(self):
        """The Cashier Shift Closeout QWeb report renders without error
        for a shift with opening/closing amounts, a payment, and a
        drop."""
        payment_code = self.env['hospitality.transaction.code'].search(
            [('transaction_type', '=', 'payment')], limit=1)
        if not payment_code:
            payment_code = self.env['hospitality.transaction.code'].create({
                'name': 'Cash Payment',
                'code': 'CASH',
                'transaction_type': 'payment',
            })

        shift = self.env['hospitality.cashier.shift'].with_user(
            self.cashier_user).create({
                'user_id': self.cashier_user.id,
                'property_id': self.property.id,
            })

        self.env['hospitality.cashier.amount'].create({
            'shift_id': shift.id,
            'kind': 'opening',
            'currency_id': self.currency_usd.id,
            'amount': 200.0,
        })

        # NOTE: posting a folio payment requires hospitality_folio's own
        # "Folio Cashier"/"Folio Supervisor" group, which this test's
        # cashier_user intentionally does NOT have (it only has this
        # module's group_cashier). That's the same cross-module group
        # gap flagged for action_approve. This test isn't validating
        # folio posting permissions, just building sample data for the
        # report, so it posts via sudo() rather than the cashier
        # persona to avoid coupling this test to hospitality_folio's
        # own group xmlids.
        self.folio.sudo()._post_payment(
            transaction_code_id=payment_code,
            amount=50.0,
            payment_ref='Test payment',
        )

        self.env['hospitality.cashier.drop'].create({
            'shift_id': shift.id,
            'amount': 20.0,
            'currency_id': self.currency_usd.id,
            'witness_user_id': self.supervisor_user.id,
        })

        self.env['hospitality.cashier.amount'].create({
            'shift_id': shift.id,
            'kind': 'closing',
            'currency_id': self.currency_usd.id,
            'amount': 230.0,
        })
        shift.action_close_shift()

        report_action = self.env.ref(
            'hospitality_cashiering.action_report_cashier_shift_closeout')
        html, report_type = self.env['ir.actions.report']._render_qweb_html(
            'hospitality_cashiering.report_cashier_shift_closeout_document',
            shift.ids,
        )
        self.assertTrue(html, "Closeout report should render HTML content.")
        self.assertEqual(report_type, 'html')
        self.assertIn(shift.name.encode(), html)