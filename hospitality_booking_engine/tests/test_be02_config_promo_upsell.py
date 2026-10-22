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
import uuid

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBE02ConfigPromoUpsell(TransactionCase):
    """BE-02: BE config, promo code and upsell model tests.

    NOTE: cls.property is always freshly created with a randomised code,
    rather than reusing an existing hospitality.property record — reusing
    an arbitrary property risks colliding with a BE config already
    persisted against it from manual UI testing or demo data.
    hospitality.property requires both 'name' and 'code'; adjust this
    payload further if it has additional required fields.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property = cls.env['hospitality.property'].create({
            'name': 'BE-02 Test Property',
            'code': f'BE02T{uuid.uuid4().hex[:6].upper()}',
        })

    def test_one_be_config_per_property(self):
        """A second config for the same property must be rejected. This
        is backed by a SQL unique constraint, but is pre-checked in the
        model's create() override before the INSERT is ever issued — so
        no savepoint gymnastics are needed to catch a clean
        ValidationError here."""
        self.env['hospitality.be.config'].create({
            'property_id': self.property.id,
        })
        with self.assertRaises(ValidationError):
            self.env['hospitality.be.config'].create({
                'property_id': self.property.id,
            })

    def test_promo_code_discount_xor(self):
        """Exactly one of discount_pct / discount_fixed must be set."""
        # Neither set.
        with self.assertRaises(ValidationError):
            self.env['hospitality.be.promo.code'].create({
                'code': 'XORNONE',
                'property_id': self.property.id,
            })
        # Both set.
        with self.assertRaises(ValidationError):
            self.env['hospitality.be.promo.code'].create({
                'code': 'XORBOTH',
                'property_id': self.property.id,
                'discount_pct': 10.0,
                'discount_fixed': 5.0,
            })
        # Exactly one set — should succeed.
        promo = self.env['hospitality.be.promo.code'].create({
            'code': 'XORONE',
            'property_id': self.property.id,
            'discount_pct': 15.0,
        })
        self.assertTrue(promo)

    def test_promo_code_max_uses_enforcement(self):
        """Promo code redemption must be rejected once used_count reaches
        max_uses — both via the _consume() helper and via a direct write
        that would push used_count past the cap."""
        promo = self.env['hospitality.be.promo.code'].create({
            'code': 'CAPPED10',
            'property_id': self.property.id,
            'discount_pct': 10.0,
            'max_uses': 2,
        })
        promo._consume()
        promo._consume()
        self.assertEqual(promo.used_count, 2)

        with self.assertRaises(ValidationError):
            promo._consume()

        with self.assertRaises(ValidationError):
            promo.write({'used_count': 5})