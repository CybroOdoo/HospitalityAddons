/** @odoo-module **/
// ---------------------------------------------------------------------------
//  NavBar patch: icon rail behaviour and the drawer button.
//
//  This only ADDS to NavBar. Odoo's own setup runs first via super(), so
//  the apps menu, breadcrumbs, sections and the systray are untouched.
// ---------------------------------------------------------------------------

import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { hasRealIcon, monogramFor, tintFor } from "./app_palette";

// The drawer draws its own full-bleed surface, so the rail steps aside
// while it is open. A body class is the least coupled way to say so.
const HOME_BODY_CLASS = "ht_on_home";

patch(NavBar.prototype, {
    setup() {
        super.setup();
        // Re-render the rail when the active app changes so the current
        // item stays marked; menuService state is not reactive.
        this.env.bus.addEventListener("MENUS:APP-CHANGED", () => this.render());
    },

    htMonogram(name) {
        return monogramFor(name);
    },

    htTint(app) {
        return tintFor(app);
    },

    /** Odoo substitutes a default icon for menus without one. */
    htIcon(app) {
        return hasRealIcon(app) ? app.webIconData : false;
    },

    /** Rail click: open the app, and make sure the drawer is dismissed. */
    onRailAppClick(app) {
        document.body.classList.remove(HOME_BODY_CLASS);
        this.menuService.selectMenu(app);
    },

    /** Apps button: open the drawer. */
    async _onClickHomeDrawer() {
        await this.actionService.doAction("hospitality_base.action_home", {
            clearBreadcrumbs: true,
        });
    },
});
