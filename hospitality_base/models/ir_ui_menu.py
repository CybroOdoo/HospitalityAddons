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
"""Hiding stock Odoo menus that this suite supersedes."""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class IrUiMenu(models.Model):
    """Adds a guarded way to retire a core menu the suite replaces."""

    _inherit = 'ir.ui.menu'

    @api.model
    def _hm_hide_superseded_menu(self, core_xmlid, replacement_xmlid):
        """Deactivate a stock Odoo menu that a hospitality menu replaces.

        Called from the data file of whichever module provides the
        replacement, so each module owns its own supersession rather than
        one list trying to know about all of them.

        Deliberately archives (active = False) rather than unlinking:

          * deleting a record another module owns is reverted the next
            time that module updates, so it would not stay hidden;
          * ``ir.ui.menu.unlink()`` promotes a deleted menu's children to
            top level, which for a root menu means scattering its whole
            subtree across the drawer;
          * archiving is reversible by anyone, from the UI, without code.

        Two guards, both of which simply skip rather than raise:

          * the core menu may not be installed at all - spreadsheet
            dashboards, for instance, arrive only through auto-installed
            bridge modules, so this must never assume it is there;
          * the REPLACEMENT must exist, so a menu is never taken away
            without the thing that takes over from it being present.

        :param str core_xmlid: the stock menu to retire.
        :param str replacement_xmlid: the hospitality menu that covers it.
        """
        core = self.env.ref(core_xmlid, raise_if_not_found=False)
        if not core:
            _logger.debug(
                "Menu %s not present; nothing to hide", core_xmlid)
            return False

        replacement = self.env.ref(
            replacement_xmlid, raise_if_not_found=False)
        if not replacement:
            _logger.warning(
                "Not hiding %s: its replacement %s is missing, and a menu "
                "must never be retired without its successor in place",
                core_xmlid, replacement_xmlid)
            return False

        if not core.active:
            return True

        core.active = False
        _logger.info(
            "Hid stock menu %s, superseded by %s", core_xmlid,
            replacement_xmlid)
        return True
