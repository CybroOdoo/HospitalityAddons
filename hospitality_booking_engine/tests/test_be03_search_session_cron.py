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
"""BE-03: search session + abandoned-cart recovery cron tests."""
import uuid
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBE03SearchSessionCron(TransactionCase):
    """BE-03: hospitality.be.search.session model and the
    cron_abandoned_cart_recovery cadence.

    NOTE: cls.property is freshly created with a randomised code, for
    the same reasons documented in the BE-02 test suite — avoiding
    collisions with pre-existing data on a shared property record.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property = cls.env['hospitality.property'].create({
            'name': 'BE-03 Test Property',
            'code': f'BE03T{uuid.uuid4().hex[:6].upper()}',
        })

    def _create_session(self, **overrides):
        vals = {
            'property_id': self.property.id,
            'visitor_id': f'visitor-{uuid.uuid4().hex[:8]}',
            'contact_email': 'guest@example.com',
            'arrival': fields.Date.today() + timedelta(days=10),
            'departure': fields.Date.today() + timedelta(days=13),
            'adults': 2,
            'children': 0,
        }
        vals.update(overrides)
        return self.env['hospitality.be.search.session'].create(vals)

    def test_session_created_on_search(self):
        """A search session is created with sane defaults: active
        state, a generated access token, and started_at /
        last_activity_at both stamped."""
        session = self._create_session()
        self.assertEqual(session.state, 'active')
        self.assertFalse(session.recovered)
        self.assertEqual(session.recovery_attempts, 0)
        self.assertTrue(session.access_token)
        self.assertTrue(session.started_at)
        self.assertTrue(session.last_activity_at)

    def test_cron_sends_1h_email(self):
        """A session idle for over 1 hour gets its first recovery
        email queued and moves to 'abandoned'."""
        session = self._create_session(
            last_activity_at=fields.Datetime.now() - timedelta(hours=2),
        )
        self.env['hospitality.be.search.session'].cron_abandoned_cart_recovery()
        session.invalidate_recordset()

        self.assertEqual(session.state, 'abandoned')
        self.assertEqual(session.recovery_attempts, 1)
        mail = self.env['mail.mail'].search([
            ('email_to', '=', 'guest@example.com'),
        ])
        self.assertTrue(mail, "Expected a recovery email to be queued.")

    def test_cron_marks_lost_after_7d(self):
        """A session that has already had its first two recovery
        emails and has now been idle 7+ days gets the final email and
        is marked 'lost'."""
        session = self._create_session(
            last_activity_at=fields.Datetime.now() - timedelta(days=8),
            recovery_attempts=2,
            state='abandoned',
        )
        self.env['hospitality.be.search.session'].cron_abandoned_cart_recovery()
        session.invalidate_recordset()

        self.assertEqual(session.state, 'lost')
        self.assertEqual(session.recovery_attempts, 3)
        mail = self.env['mail.mail'].search([
            ('email_to', '=', 'guest@example.com'),
        ])
        self.assertTrue(mail, "Expected the final recovery email to be queued.")

    def test_recovered_when_reservation_matches(self):
        """A session is marked recovered once its details match a
        confirmed reservation."""
        arrival = fields.Date.today() + timedelta(days=10)
        departure = fields.Date.today() + timedelta(days=13)
        session = self._create_session(arrival=arrival, departure=departure)

        matched = self.env['hospitality.be.search.session']._recover_for_confirmed_reservation(
            property_id=self.property.id,
            contact_email='guest@example.com',
            arrival=arrival,
            departure=departure,
        )
        self.assertIn(session, matched)

        session.invalidate_recordset()
        self.assertTrue(session.recovered)
        self.assertEqual(session.state, 'recovered')