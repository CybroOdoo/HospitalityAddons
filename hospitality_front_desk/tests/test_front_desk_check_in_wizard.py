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
from unittest.mock import patch, MagicMock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestFrontDeskCheckInWizard(TransactionCase):
    """FD-02 acceptance tests for the check-in wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Reservation = cls.env['hospitality.reservation']

        # ── Partner ───────────────────────────────────────────────────
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Guest FD02'
        })

        # ── ID document — pick first valid selection key dynamically ──
        id_doc_field = cls.env['hospitality.guest.id.document']._fields.get('type')
        doc_type_key = (
            id_doc_field.selection[0][0]
            if id_doc_field and id_doc_field.selection
            else 'passport'
        )
        cls.id_doc = cls.env['hospitality.guest.id.document'].create({
            'partner_id': cls.partner.id,
            'type': doc_type_key,
            'number': 'AB123456',
        })

        # ── Use an existing valid reservation template if possible ────
        cls.template_reservation = Reservation.search([
            ('property_id', '!=', False),
            ('space_type_id', '!=', False),
            ('rate_code_id', '!=', False),
        ], limit=1)

        if not cls.template_reservation:
            raise Exception(
                "No valid reservation template found with property_id, "
                "space_type_id and rate_code_id. Install hospitality_reservation "
                "demo data first."
            )

        cls.property = cls.template_reservation.property_id
        cls.space_type = cls.template_reservation.space_type_id
        cls.rate_code = cls.template_reservation.rate_code_id

        # ── Space — create a fresh one for the exact property/type ────
        cls.space = cls.env['hospitality.space'].create({
            'name': '101-FD02',
            'code': '101FD02',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'status': 'vacant_clean',
        })

        # ── Reservation fixture: copy a valid reservation ─────────────
        defaults = {
            'partner_id': cls.partner.id,
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'rate_code_id': cls.rate_code.id,
        }

        # Keep a non-walk-in scenario for ID document validation
        if 'is_walkin' in Reservation._fields:
            defaults['is_walkin'] = False

        source_field = Reservation._fields.get('source')
        if source_field and getattr(cls.template_reservation, 'source', False) == 'walk_in':
            non_walkin = next(
                (key for key, _label in source_field.selection if key != 'walk_in'),
                False
            )
            if non_walkin:
                defaults['source'] = non_walkin

        state_field = Reservation._fields.get('state')
        if state_field and not state_field.compute:
            defaults['state'] = 'confirmed'

        # Clear fields that should not be reused from template
        if 'space_id' in Reservation._fields:
            defaults['space_id'] = False
        if 'folio_id' in Reservation._fields:
            defaults['folio_id'] = False

        cls.reservation = cls.template_reservation.copy(defaults)

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────
    def _wizard_vals(self, **kwargs):
        vals = {
            'reservation_id': self.reservation.id,
            'space_id': self.space.id,
            'id_document_ids': [(4, self.id_doc.id)],
            'payment_method': 'none',
        }
        vals.update(kwargs)
        return vals

    def _make_wizard(self, **kwargs):
        return self.env['hospitality.front.desk.check.in.wizard'].create(
            self._wizard_vals(**kwargs)
        )

    # ─────────────────────────────────────────────────────────────────
    # 1. Space availability validation
    # ─────────────────────────────────────────────────────────────────
    def test_check_in_validates_space_availability(self):
        """Wizard must raise if space_id is missing."""
        wiz = self.env['hospitality.front.desk.check.in.wizard'].new(
            self._wizard_vals()
        )
        wiz.space_id = False
        with self.assertRaises(UserError):
            wiz.action_check_in()

    # ─────────────────────────────────────────────────────────────────
    # 2. Deposit / payment method validation
    # ─────────────────────────────────────────────────────────────────
    def test_check_in_validates_deposit_met(self):
        """If deposit_amount > 0 and method == 'none', raise UserError."""
        with self.assertRaises(UserError):
            wiz = self._make_wizard(
                deposit_amount=100.0,
                payment_method='none',
            )
            wiz.action_check_in()

    # ─────────────────────────────────────────────────────────────────
    # 3. Delegation to reservation.action_check_in
    # ─────────────────────────────────────────────────────────────────
    def test_check_in_calls_reservation_action(self):
        """action_check_in must delegate to reservation.action_check_in()."""
        wiz = self._make_wizard(payment_method='none', deposit_amount=0.0)
        with patch.object(
            type(self.reservation),
            'action_check_in',
            return_value=None,
        ) as mock_ci:
            wiz.action_check_in()
            mock_ci.assert_called_once()

    # ─────────────────────────────────────────────────────────────────
    # 4. Registration card report opened when requested
    # ─────────────────────────────────────────────────────────────────
    def test_check_in_prints_reg_card_when_requested(self):
        """When print_reg_card=True and the report ref exists, a report
        action dict must be returned."""
        wiz = self._make_wizard(
            print_reg_card=True,
            payment_method='none',
            deposit_amount=0.0,
        )

        fake_action = {'type': 'ir.actions.report', 'report_name': 'stub'}
        mock_report = MagicMock()
        mock_report.report_action.return_value = fake_action

        with patch.object(
            type(self.reservation), 'action_check_in', return_value=None
        ):
            with patch.object(
                type(wiz.env),
                'ref',
                return_value=mock_report,
            ):
                result = wiz.action_check_in()

        self.assertEqual(result, fake_action)

    # ─────────────────────────────────────────────────────────────────
    # 5. ID document requirement
    # ─────────────────────────────────────────────────────────────────
    def test_check_in_requires_id_document(self):
        """Non-walk-in reservation without ID documents must raise."""
        wiz = self.env['hospitality.front.desk.check.in.wizard'].new(
            self._wizard_vals()
        )
        wiz.id_document_ids = self.env['hospitality.guest.id.document']
        with self.assertRaises(UserError):
            wiz.action_check_in()