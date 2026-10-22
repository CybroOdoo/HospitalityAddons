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
"""Protect the seeded folio records now that they are demo-only data.

demo/demo_folios.xml used to be listed under BOTH "data" and "demo" in the
manifest, so its records - a property, three partners, four folios, their
lines and a routing instruction - were installed into every database,
production included. It is now listed under "demo" alone.

That change alone is destructive on an existing database. At the end of a
module update Odoo calls ir.model.data._process_end(), which deletes any
record this module created and no longer declares. The seeded property is
referenced by rooms, reservations and folios, so the DELETE either fails
with a foreign-key violation and aborts the whole upgrade, or succeeds and
takes real data with it.

_process_end() skips rows flagged noupdate, and rows loaded from a demo
file are flagged that way anyway - so this marks the existing rows the way
a demo load would have, which both protects them and leaves them where
they now belong. Nothing is deleted and nothing is re-created; databases
that already have this data simply keep it.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install: the records are created by the demo loader, which
        # sets noupdate itself.
        return

    cr.execute(
        r"""
        UPDATE ir_model_data
           SET noupdate = TRUE
         WHERE module = 'hospitality_folio'
           AND name LIKE 'demo\_%%'
           AND COALESCE(noupdate, FALSE) = FALSE
        """
    )
    if cr.rowcount:
        _logger.info(
            "Flagged %d seeded folio record(s) as noupdate so moving "
            "demo_folios.xml out of the manifest's data list does not "
            "delete them.", cr.rowcount,
        )
