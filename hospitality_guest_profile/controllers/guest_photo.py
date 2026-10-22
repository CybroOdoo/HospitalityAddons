
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

from odoo import http
from odoo.http import request, Response

class GuestPhotoController(http.Controller):
    """
    HTTP controller that serves guest avatar thumbnails.

    Route:  GET /hospitality/guest/<int:partner_id>/photo
    Auth:   user (session required)
    Return: 256×256 image bytes with public cache-control (300 s)
            404 if the partner is not a guest or has no image
    """
    @http.route(
        "/hospitality/guest/<int:partner_id>/photo",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def guest_photo(self, partner_id, **kwargs):
        """Return the image_256 thumbnail for a guest partner.
        Returns 200 + image bytes when:
        - the partner exists
        - is_guest is True
        - image_256 is set
        Returns 404 in every other case (unknown partner, not a guest,
        no image stored).
        """
        partner = (
            request.env["res.partner"]
            .sudo()
            .search([("id", "=", partner_id), ("is_guest", "=", True)], limit=1)
        )
        if not partner or not partner.image_256:
            return request.not_found()
        import base64
        image_bytes = base64.b64decode(partner.image_256)
        mime = "image/png" if image_bytes[:4] == b"\x89PNG" else "image/jpeg"
        headers = [
            ("Content-Type", mime),
            ("Content-Length", str(len(image_bytes))),
            ("Cache-Control", "public, max-age=300"),
        ]
        return Response(image_bytes, status=200, headers=headers)
