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
"""
GUEST-07 — Controller tests for GET /hospitality/guest/<id>/photo.

Tests
-----
* test_photo_controller_returns_404_for_non_guest
* test_photo_controller_returns_200_when_image_present
* test_photo_controller_returns_404_for_guest_without_image   (edge case)
* test_photo_controller_returns_404_for_unknown_partner        (edge case)
* test_photo_controller_content_type_is_image                   (header check)
"""

import base64

from odoo.tests import HttpCase, tagged


# Minimal valid 1×1 red PNG — small enough to store, valid enough to decode
_TINY_RED_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)


@tagged("post_install", "-at_install", "hospitality_guest_profile")
class TestGuestPhotoController(HttpCase):
    """HTTP-level tests for the guest photo thumbnail endpoint."""

    def setUp(self):
        """Log in so url_open() carries an authenticated session.

        The route is declared auth="user", so unauthenticated requests are
        303-redirected to /web/login and url_open() follows that redirect,
        returning the login page instead of hitting the controller.
        """
        super().setUp()
        self.authenticate("1", "1")

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _make_guest(self, name="Test Guest", with_image=False):
        """Create a minimal is_guest=True partner, optionally with image_1920 (which populates image_256)."""
        vals = {"name": name, "is_guest": True}
        if with_image:
            vals["image_1920"] = _TINY_RED_PNG_B64
        return self.env["res.partner"].create(vals)

    def _make_non_guest(self, name="Regular Partner"):
        """Create a normal partner with is_guest=False."""
        return self.env["res.partner"].create({"name": name, "is_guest": False})

    def _photo_url(self, partner_id):
        return f"/hospitality/guest/{partner_id}/photo"

    # ------------------------------------------------------------------ #
    # Required tests (GUEST-07 spec)                                      #
    # ------------------------------------------------------------------ #

    def test_photo_controller_returns_404_for_non_guest(self):
        """
        Given  a partner that exists but is_guest = False
        When   GET /hospitality/guest/<id>/photo
        Then   response status is 404
        """
        partner = self._make_non_guest("Not A Guest")
        response = self.url_open(self._photo_url(partner.id))
        self.assertEqual(
            response.status_code,
            404,
            f"Expected 404 for non-guest partner {partner.id}, "
            f"got {response.status_code}",
        )

    def test_photo_controller_returns_200_when_image_present(self):
        """
        Given  a guest partner with image_1920 populated
        When   GET /hospitality/guest/<id>/photo
        Then   response status is 200
        And    body equals the decoded image bytes
        And    Cache-Control contains 'public' and 'max-age=300'
        """
        guest = self._make_guest("Photogenic Guest", with_image=True)
        response = self.url_open(self._photo_url(guest.id))

        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200 for guest with image, got {response.status_code}",
        )

        # Body must be the exact decoded bytes
        expected = base64.b64decode(_TINY_RED_PNG_B64)
        self.assertEqual(
            response.content,
            expected,
            "Response body does not match the stored image bytes",
        )

        # Cache-Control header
        cc = response.headers.get("Cache-Control", "")
        self.assertIn("public", cc,
                      f"Cache-Control missing 'public': {cc}")
        self.assertIn("max-age=300", cc,
                      f"Cache-Control missing 'max-age=300': {cc}")

    # ------------------------------------------------------------------ #
    # Edge-case tests                                                      #
    # ------------------------------------------------------------------ #

    def test_photo_controller_returns_404_for_guest_without_image(self):
        """
        Given  a guest partner with no image_1920
        When   GET /hospitality/guest/<id>/photo
        Then   response status is 404
        """
        guest = self._make_guest("Imageless Guest", with_image=False)
        response = self.url_open(self._photo_url(guest.id))
        self.assertEqual(
            response.status_code,
            404,
            f"Expected 404 for guest with no image, got {response.status_code}",
        )

    def test_photo_controller_returns_404_for_unknown_partner(self):
        """
        Given  a partner_id that does not exist
        When   GET /hospitality/guest/<id>/photo
        Then   response status is 404
        """
        response = self.url_open(self._photo_url(999_999_999))
        self.assertEqual(
            response.status_code,
            404,
            f"Expected 404 for non-existent partner, got {response.status_code}",
        )

    def test_photo_controller_content_type_is_image(self):
        """
        Given  a guest with a PNG image
        When   GET /hospitality/guest/<id>/photo
        Then   Content-Type header starts with 'image/'
        """
        guest = self._make_guest("PNG Guest", with_image=True)
        response = self.url_open(self._photo_url(guest.id))
        ct = response.headers.get("Content-Type", "")
        self.assertTrue(
            ct.startswith("image/"),
            f"Expected image/* Content-Type, got: {ct}",
        )