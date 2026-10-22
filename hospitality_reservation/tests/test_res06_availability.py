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

"""RES-06 — Availability MV wiring tests.

Tests cover:
  * test_count_reserved_counts_confirmed_and_checked_in_only
  * test_count_reserved_ignores_cancelled_and_no_show
  * test_mv_refresh_after_reservation_create
  * test_availability_decreases_when_reservation_confirmed
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAvailabilityMVWiring(TransactionCase):
    """RES-06: _count_reserved override and MV availability wiring."""

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Grant supervisor rights to the test user so guarded actions
        # (action_no_show, undo_check_in) work without a separate sudo().
        supervisor_group = cls.env.ref(
            'hospitality_reservation.group_reservation_supervisor'
        )
        cls.env.user.write({'group_ids': [(4, supervisor_group.id)]})

        cls.property = cls.env['hospitality.property'].create({
            'name': 'RES-06 Test Hotel',
            'code': 'R06H',
        })
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'Standard',
            'code': 'STD',
            'property_id': cls.property.id,
        })
        cls.space_type_b = cls.env['hospitality.space.type'].create({
            'name': 'Suite',
            'code': 'STE',
            'property_id': cls.property.id,
        })
        # Two physical spaces so availability > 0
        cls.space1 = cls.env['hospitality.space'].create({
            'name': '101', 'code': 'RM101',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })
        cls.space2 = cls.env['hospitality.space'].create({
            'name': '102', 'code': 'RM102',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })
        cls.rate_code = cls.env['hospitality.rate.code'].create({
            'name': 'BAR', 'code': 'BAR',
            'property_id': cls.property.id,
        })
        cls.guest = cls.env['res.partner'].create({'name': 'Test Guest R06'})
        cls.today = date.today()

    def _make_res(self, arrival_offset=1, departure_offset=3,
                  space=None, state='confirmed'):
        """Create a reservation and optionally confirm/check-in it."""
        res = self.env['hospitality.reservation'].create({
            'property_id': self.property.id,
            'partner_id': self.guest.id,
            'arrival': self.today + timedelta(days=arrival_offset),
            'departure': self.today + timedelta(days=departure_offset),
            'space_type_id': self.space_type.id,
            'space_id': (space or self.space1).id,
            'rate_code_id': self.rate_code.id,
            'adults': 1,
        })
        if state == 'confirmed':
            res.action_confirm()
        elif state == 'checked_in':
            res.action_confirm()
            res.write({'deposit_paid': res.total_amount or 1.0})
            res.action_check_in()
        return res

    def _count(self, the_date, space_type_id=None):
        """Call _count_reserved on the test property."""
        st_id = space_type_id or self.space_type.id
        return self.property._count_reserved(st_id, the_date)

    # ------------------------------------------------------------------
    # test_count_reserved_counts_confirmed_and_checked_in_only
    # ------------------------------------------------------------------

    def test_count_reserved_counts_confirmed_and_checked_in_only(self):
        """_count_reserved must count confirmed and checked_in reservations."""
        target_date = self.today + timedelta(days=2)

        # Confirmed reservation overlapping target_date
        confirmed = self._make_res(arrival_offset=1, departure_offset=4,
                                   state='confirmed')
        count_after_confirm = self._count(target_date)
        self.assertGreaterEqual(
            count_after_confirm, 1,
            '_count_reserved must include confirmed reservations.'
        )

        # Checked-in reservation also overlapping target_date
        checked_in = self._make_res(arrival_offset=1, departure_offset=4,
                                    space=self.space2, state='checked_in')
        count_after_checkin = self._count(target_date)
        self.assertGreater(
            count_after_checkin, count_after_confirm,
            '_count_reserved must also include checked_in reservations.'
        )

        # Clean up so other tests start fresh
        confirmed.write({'state': 'cancelled'})
        checked_in.write({'state': 'cancelled'})

    # ------------------------------------------------------------------
    # test_count_reserved_ignores_cancelled_and_no_show
    # ------------------------------------------------------------------

    def test_count_reserved_ignores_cancelled_and_no_show(self):
        """_count_reserved must NOT count cancelled or no-show reservations."""
        target_date = self.today + timedelta(days=2)

        baseline = self._count(target_date)

        # Create and then cancel a reservation
        res = self._make_res(arrival_offset=1, departure_offset=4,
                              state='confirmed')
        count_confirmed = self._count(target_date)
        self.assertGreater(count_confirmed, baseline,
                           'Confirmed reservation must raise count.')

        res.action_cancel()
        count_after_cancel = self._count(target_date)
        self.assertEqual(
            count_after_cancel, baseline,
            'Cancelled reservation must NOT be counted by _count_reserved.'
        )

        # Create and mark no_show
        res2 = self._make_res(arrival_offset=1, departure_offset=4,
                               state='confirmed')
        res2.action_no_show()
        count_after_noshow = self._count(target_date)
        self.assertEqual(
            count_after_noshow, baseline,
            'No-show reservation must NOT be counted by _count_reserved.'
        )

    # ------------------------------------------------------------------
    # test_mv_refresh_after_reservation_create
    # ------------------------------------------------------------------

    def test_mv_refresh_after_reservation_create(self):
        """Creating a confirmed reservation marks the MV for refresh.

        We cannot assert on the MV content directly (it may not be installed
        in the test environment), so we verify that:
          (a) the trigger/queue mechanism does not raise an error, and
          (b) _count_reserved returns the expected value immediately after
              the reservation is created (the method queries the live table,
              not the MV, so it is always current).
        """
        target_date = self.today + timedelta(days=2)
        baseline = self._count(target_date)

        res = self._make_res(arrival_offset=1, departure_offset=4,
                              state='confirmed')

        count_after = self._count(target_date)
        self.assertEqual(
            count_after, baseline + 1,
            'Creating a confirmed reservation must increase _count_reserved by 1.'
        )

        # Attempt MV refresh — OK if the view is absent (just logs a warning)
        try:
            self.property._refresh_availability_mv()
        except Exception as e:
            self.fail(
                f'_refresh_availability_mv raised an unexpected exception: {e}'
            )

        # Clean up
        res.action_cancel()

    # ------------------------------------------------------------------
    # test_availability_decreases_when_reservation_confirmed
    # ------------------------------------------------------------------

    def test_availability_decreases_when_reservation_confirmed(self):
        """Confirming a reservation reduces _count_reserved; cancelling restores it.

        This is the core acceptance test: confirm -> count goes up by 1,
        cancel -> count returns to baseline.  The MV would reflect the same
        change after a REFRESH, but we test the underlying data source here
        to avoid depending on the MV being installed.
        """
        target_date = self.today + timedelta(days=2)
        baseline = self._count(target_date)

        # Draft reservation — must NOT count
        draft = self.env['hospitality.reservation'].create({
            'property_id': self.property.id,
            'partner_id': self.guest.id,
            'arrival': self.today + timedelta(days=1),
            'departure': self.today + timedelta(days=4),
            'space_type_id': self.space_type.id,
            'space_id': self.space1.id,
            'rate_code_id': self.rate_code.id,
            'adults': 1,
        })
        count_draft = self._count(target_date)
        self.assertEqual(count_draft, baseline,
                         'Draft reservation must NOT affect _count_reserved.')

        # Confirm — must count
        draft.action_confirm()
        count_confirmed = self._count(target_date)
        self.assertEqual(
            count_confirmed, baseline + 1,
            'Confirming a reservation must increase _count_reserved by 1.'
        )

        # Cancel — must restore
        draft.action_cancel()
        count_cancelled = self._count(target_date)
        self.assertEqual(
            count_cancelled, baseline,
            'Cancelling a reservation must restore _count_reserved to baseline.'
        )