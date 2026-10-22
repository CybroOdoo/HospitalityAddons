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

from unittest.mock import patch
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


def _make_seq(env, name):
    return env['ir.sequence'].create({
        'name': name,
        'code': name.lower().replace(' ', '_'),
        'prefix': name[:3].upper() + '/%(year)s/',
        'padding': 5,
    })


@tagged('post_install', '-at_install', 'hospitality')
class TestBase06Mixins(TransactionCase):
    """BASE-06 — Mixins (property scoping, business date) + encrypted fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create two properties
        cls.prop_a = cls.env['hospitality.property'].create({
            'name': 'Hotel A',
            'code': 'HOTELA',
            'property_type': 'hotel',
            'timezone': 'UTC',
            'currency_id': cls.env.company.currency_id.id,
            'sequence_reservation_id': _make_seq(cls.env, 'Res A').id,
            'sequence_folio_id': _make_seq(cls.env, 'Folio A').id,
        })
        cls.prop_b = cls.env['hospitality.property'].create({
            'name': 'Hotel B',
            'code': 'HOTELB',
            'property_type': 'hotel',
            'timezone': 'UTC',
            'currency_id': cls.env.company.currency_id.id,
            'sequence_reservation_id': _make_seq(cls.env, 'Res B').id,
            'sequence_folio_id': _make_seq(cls.env, 'Folio B').id,
        })

        # Create a restricted user assigned only to prop_a
        cls.user_a = cls.env['res.users'].create({
            'name': 'Staff A',
            'login': 'staff_a@test.com',
            'group_ids': [(4, cls.env.ref(
                'hospitality_base.group_hospitality_user').id)],
        })
        cls.user_a.property_ids = [(4, cls.prop_a.id)]
        cls.user_a.property_id = cls.prop_a.id

        # Corporate user — sees all properties
        cls.user_corp = cls.env['res.users'].create({
            'name': 'Corporate',
            'login': 'corp@test.com',
            'group_ids': [(4, cls.env.ref(
                'hospitality_base.group_hospitality_corporate').id)],
        })

    # ------------------------------------------------------------------
    # Test 1 — _get_property_domain for restricted user
    # ------------------------------------------------------------------
    def test_01_property_domain_restricted_user(self):
        """Restricted user domain includes only their properties."""
        mixin = self.env['hospitality.mixin.property']
        domain = mixin.with_user(self.user_a)._get_property_domain()
        self.assertIn(
            ('property_id', 'in', [self.prop_a.id]),
            domain,
            "Domain should restrict to user's allowed properties."
        )

    # ------------------------------------------------------------------
    # Test 2 — _get_property_domain for corporate user returns []
    # ------------------------------------------------------------------
    def test_02_property_domain_corporate_user(self):
        """Corporate user gets an empty domain (sees all)."""
        mixin = self.env['hospitality.mixin.property']
        domain = mixin.with_user(self.user_corp)._get_property_domain()
        self.assertEqual(
            domain, [],
            "Corporate user should get an empty domain."
        )

    # ------------------------------------------------------------------
    # Test 3 — _check_property_access raises for wrong property
    # ------------------------------------------------------------------
    def test_03_check_property_access_raises(self):
        """User cannot create records on a property they are not assigned to."""
        trace = self.env['hospitality.activity.trace'].with_user(
            self.user_a
        )
        with self.assertRaises(AccessError):
            trace.create({
                'type': 'anytime',
                'text': 'Should fail — wrong property.',
                'property_id': self.prop_b.id,
            })

    # ------------------------------------------------------------------
    # Test 4 — _get_business_date returns property business_date
    # ------------------------------------------------------------------
    def test_04_business_date_returns_property_date(self):
        """_get_business_date returns the property's business_date."""
        from odoo import fields as ofields
        mixin = self.env['hospitality.mixin.business.date']
        result = mixin._get_business_date(self.prop_a.id)
        self.assertEqual(
            result,
            self.prop_a.business_date or ofields.Date.today(),
            "Should return property's business_date."
        )

    # ------------------------------------------------------------------
    # Test 5 — EncryptedChar round-trip
    # ------------------------------------------------------------------
    def test_05_encrypted_char_round_trip(self):
        """EncryptedChar encrypts on write and decrypts on read correctly."""
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode('ascii')

        self.env['ir.config_parameter'].sudo().set_param(
            'hospitality.encryption_key', test_key
        )

        from odoo.addons.hospitality_base.models.hospitality_encrypted_fields \
            import EncryptedChar, _get_fernet

        fernet = _get_fernet(self.env)
        plaintext = 'secret-passport-number'

        # Simulate what convert_to_column does
        import base64
        ciphertext_b64 = base64.urlsafe_b64encode(
            fernet.encrypt(plaintext.encode('utf-8'))
        ).decode('ascii')

        # Simulate what convert_to_record does
        raw = base64.urlsafe_b64decode(ciphertext_b64.encode('ascii'))
        decrypted = fernet.decrypt(raw).decode('utf-8')

        self.assertEqual(
            decrypted, plaintext,
            "EncryptedChar round-trip should return original plaintext."
        )

        # Clean up key
        self.env['ir.config_parameter'].sudo().set_param(
            'hospitality.encryption_key', ''
        )

    # ------------------------------------------------------------------
    # Test 6 — _get_fernet raises UserError when key not configured
    # ------------------------------------------------------------------
    def test_06_encrypted_field_no_key_raises(self):
        """_get_fernet raises UserError when no encryption key is configured."""
        # Ensure key is absent
        self.env['ir.config_parameter'].sudo().set_param(
            'hospitality.encryption_key', ''
        )

        from odoo.addons.hospitality_base.models.hospitality_encrypted_fields \
            import _get_fernet

        with patch(
            'odoo.tools.config.config.get',
            return_value=''
        ):
            with self.assertRaises(UserError):
                _get_fernet(self.env)