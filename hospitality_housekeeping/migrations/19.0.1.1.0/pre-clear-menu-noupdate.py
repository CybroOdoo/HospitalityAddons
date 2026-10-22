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
"""Clear the stale ``noupdate`` flag on this module's menu records.

``housekeeping_menus.xml`` used to be wrapped in ``<data noupdate="1">``.
``noupdate`` is stored per record in ``ir_model_data``, not read from the
XML on each upgrade, so simply removing the attribute from the file does
nothing to a database that already has those rows: Odoo still skips them
and every later change to the menu tree applies to fresh installs only.

That is how Housekeeping stayed a child of Rooms through an upgrade that
had already promoted it to a root. The flag has to be cleared once, in
the database, before the data file can take effect.

This is a PRE migration on purpose. Odoo runs pre- scripts before the
module's data files and post- scripts after them, so a post- script
would clear the flag only once the XML had already been skipped - the
restructure would need a second upgrade to land. Clearing it first makes
one upgrade enough.

Safe to re-run: it only ever flips true to false, and the XML no longer
asks for noupdate on any of these records.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE ir_model_data
           SET noupdate = FALSE
         WHERE module = 'hospitality_housekeeping'
           AND model = 'ir.ui.menu'
           AND noupdate = TRUE
    """)
    _logger.info(
        "hospitality_housekeeping: cleared noupdate on %s menu records; "
        "the menu tree in housekeeping_menus.xml now applies on upgrade",
        cr.rowcount,
    )
