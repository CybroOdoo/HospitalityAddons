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
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.fields import Date


@tagged('post_install', '-at_install')
class TestHkLinenCountVariance(TransactionCase):
    """Covers hospitality.linen.count / .line: variance computation
    and the draft/posted lifecycle.

    NOTE: property fixtures use only a minimal field set (name/code).
    Adjust setUpClass if hospitality.property carries other required
    fields in this database.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.LinenCount = cls.env['hospitality.linen.count']
        cls.LinenCountLine = cls.env['hospitality.linen.count.line']

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'HK Linen Test Property',
                'code': 'HKLINTEST',
            })

        cls.product = cls.env['product.product'].search([], limit=1)
        if not cls.product:
            cls.product = cls.env['product.product'].create({
                'name': 'HK Test Bath Towel',
            })

    def test_linen_count_variance_computation(self):
        """variance_qty = counted_qty - expected_qty, and updates
        when either quantity changes."""
        count = self.LinenCount.create({
            'property_id': self.property.id,
            'count_date': Date.today(),
        })
        line = self.LinenCountLine.create({
            'count_id': count.id,
            'product_id': self.product.id,
            'expected_qty': 50,
            'counted_qty': 47,
        })
        self.assertEqual(line.variance_qty, -3)

        line.counted_qty = 50
        self.assertEqual(line.variance_qty, 0)

        line.expected_qty = 40
        self.assertEqual(line.variance_qty, 10)

    def test_cannot_post_without_lines(self):
        """A linen count with no lines can't be posted."""
        count = self.LinenCount.create({
            'property_id': self.property.id,
            'count_date': Date.today(),
        })
        with self.assertRaises(UserError):
            count.action_post()
        self.assertEqual(count.state, 'draft')

    def test_post_and_reset_to_draft(self):
        """A count with at least one line can be posted, and reset
        back to draft for corrections."""
        count = self.LinenCount.create({
            'property_id': self.property.id,
            'count_date': Date.today(),
        })
        self.LinenCountLine.create({
            'count_id': count.id,
            'product_id': self.product.id,
            'expected_qty': 20,
            'counted_qty': 20,
        })
        count.action_post()
        self.assertEqual(count.state, 'posted')

        count.action_reset_to_draft()
        self.assertEqual(count.state, 'draft')

    def test_line_cascade_deleted_with_count(self):
        """Deleting a linen count deletes its lines (ondelete=cascade)."""
        count = self.LinenCount.create({
            'property_id': self.property.id,
            'count_date': Date.today(),
        })
        line = self.LinenCountLine.create({
            'count_id': count.id,
            'product_id': self.product.id,
            'expected_qty': 5,
            'counted_qty': 5,
        })
        line_id = line.id
        count.unlink()
        self.assertFalse(self.LinenCountLine.search([('id', '=', line_id)]))