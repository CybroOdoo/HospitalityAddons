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
from datetime import date, timedelta

from odoo.orm.registry import Registry
from odoo.tests import HttpCase, tagged

# Dedicated credentials — login == password satisfies HttpCase.authenticate()
_TOUR_LOGIN    = 'hres03_tour'
_TOUR_PASSWORD = 'hres03_tour'


@tagged('post_install', '-at_install')
class TestTapeChartTours(HttpCase):
    """RES-03: Tape Chart browser tour tests.

    Authentication strategy
    -----------------------
    HttpCase.start_tour(login=X) calls authenticate(X, X) — password must
    equal the login name.  We never touch the real admin password (published
    module — every customer DB has a different one).

    We create a dedicated tour user via a *separate* registry cursor that is
    committed independently of the test savepoint.  Odoo 19 forbids
    cr.commit() on the test cursor but explicitly allows opening another
    cursor for exactly this purpose.  The user is deleted in tearDown via
    another independent cursor, leaving no permanent side-effects.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _registry_cursor(self):
        """Open a fresh, commit-capable cursor from the ORM registry."""
        return Registry(self.env.cr.dbname).cursor()

    def _create_tour_user(self):
        """Create the tour user in its own committed transaction so the
        browser's separate DB connection can authenticate with it."""
        agent_group = self.env.ref(
            'hospitality_reservation.group_reservation_agent'
        )
        user_vals = {
            'name': 'Tape Chart Tour User',
            'login': _TOUR_LOGIN,
            'password': _TOUR_PASSWORD,
            'group_ids': [(4, agent_group.id)],
        }
        if 'property_ids' in self.env['res.users']._fields:
            user_vals['property_ids'] = [(4, self.property.id)]

        with self._registry_cursor() as cr:
            env2 = self.env(cr=cr)
            # Remove any stale user left by a previously interrupted run.
            stale = env2['res.users'].search([('login', '=', _TOUR_LOGIN)])
            stale.unlink()
            user = env2['res.users'].create(user_vals)
            uid = user.id
            cr.commit()
        return uid

    def _delete_tour_user(self, uid):
        """Delete the tour user in its own committed transaction."""
        with self._registry_cursor() as cr:
            env2 = self.env(cr=cr)
            env2['res.users'].browse(uid).unlink()
            cr.commit()

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.property = cls.env['hospitality.property'].create({
            'name': 'Tour Test Hotel',
            'code': 'TTH01',
        })
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'Standard Room',
            'code': 'STD',
            'property_id': cls.property.id,
        })
        cls.spaces = cls.env['hospitality.space'].create([
            {
                'name': f'10{i}',
                'code': f'RM10{i}',
                'property_id': cls.property.id,
                'space_type_id': cls.space_type.id,
            }
            for i in range(1, 4)
        ])
        cls.rate_code = cls.env['hospitality.rate.code'].create({
            'name': 'BAR',
            'code': 'BAR',
            'property_id': cls.property.id,
        })
        cls.guest = cls.env['res.partner'].create({'name': 'Tour Guest'})

        cls.today = date.today()
        cls.reservation = cls.env['hospitality.reservation'].create({
            'property_id': cls.property.id,
            'partner_id': cls.guest.id,
            'arrival': cls.today + timedelta(days=1),
            'departure': cls.today + timedelta(days=3),
            'space_type_id': cls.space_type.id,
            'space_id': cls.spaces[0].id,
            'rate_code_id': cls.rate_code.id,
            'adults': 2,
            'state': 'confirmed',
        })

    def setUp(self):
        super().setUp()
        self._tour_uid = self._create_tour_user()

    def tearDown(self):
        super().tearDown()
        self._delete_tour_user(self._tour_uid)

    # ------------------------------------------------------------------
    # Tours
    # ------------------------------------------------------------------

    def test_tape_chart_renders(self):
        """Tape chart mounts with date header, row labels, and the seeded bar."""
        self.start_tour(
            '/odoo/action-hospitality_reservation.action_tape_chart',
            'test_tape_chart_renders',
            login=_TOUR_LOGIN,
        )

    def test_drag_to_create_opens_new_reservation_form(self):
        """Dragging across an empty cell range opens a pre-filled new reservation form."""
        self.start_tour(
            '/odoo/action-hospitality_reservation.action_tape_chart',
            'test_drag_to_create_opens_new_reservation_form',
            login=_TOUR_LOGIN,
        )

    def test_drag_to_extend_persists_dates(self):
        """Dragging a bar's resize handle extends the reservation and persists via write()."""
        self.start_tour(
            '/odoo/action-hospitality_reservation.action_tape_chart',
            'test_drag_to_extend_persists_dates',
            login=_TOUR_LOGIN,
        )
        self.reservation.invalidate_recordset()
        self.assertGreater(
            self.reservation.departure,
            self.today + timedelta(days=3),
            'Expected the departure date to have moved further out after the drag.',
        )

    def test_drag_vertical_changes_space(self):
        """Dragging a bar vertically reassigns it to another space (direct write,
        since the seeded reservation is confirmed not checked_in)."""
        self.start_tour(
            '/odoo/action-hospitality_reservation.action_tape_chart',
            'test_drag_vertical_changes_space',
            login=_TOUR_LOGIN,
        )
        self.reservation.invalidate_recordset()
        self.assertNotEqual(
            self.reservation.space_id.id,
            self.spaces[0].id,
            'Expected the reservation to have moved to a different space after the drag.',
        )