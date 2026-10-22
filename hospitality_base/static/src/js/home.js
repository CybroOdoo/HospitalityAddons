/** @odoo-module **/
// ---------------------------------------------------------------------------
//  App drawer / landing page.
//
//  Apps come from the menu service, which returns only the roots the
//  user may open, so a tile can never lead somewhere they cannot go.
// ---------------------------------------------------------------------------

import { Component, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { hasRealIcon, monogramFor, tintFor } from "./app_palette";

// The drawer is a full-bleed surface; the rail steps aside for it.
const HOME_BODY_CLASS = "ht_on_home";

export class HospitalityHome extends Component {
    static template = "hospitality_base.Home";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.menuService = useService("menu");
        this.searchRef = useRef("search");

        this.state = useState({ loading: true, query: "", data: {}, clock: "" });

        document.body.classList.add(HOME_BODY_CLASS);
        onWillUnmount(() => {
            document.body.classList.remove(HOME_BODY_CLASS);
            this._stopClock();
        });

        onWillStart(async () => {
            try {
                this.state.data = await this.orm.call(
                    "hospitality.theme.home", "get_home_data", [], {}
                );
                this._startClock();
            } catch (error) {
                // The grid is the part people cannot work without, so the
                // drawer still opens if the aggregator fails.
                console.warn("Hospitality theme: home data failed", error);
                this.state.data = { stats: [] };
            } finally {
                this.state.loading = false;
            }
        });
    }

    /**
     * Tick the clock forward from the server's reading.
     *
     * Deliberately NOT `new Date()`: the date beside it is rendered
     * server-side in the user's timezone, and a browser in another
     * timezone would show a time that contradicts it. Taking the
     * server's minutes-since-midnight and adding the elapsed wall time
     * keeps both in the same timezone.
     *
     * Fifteen seconds is frequent enough that a minute never looks
     * stale, and cheap: it touches one reactive string, nothing else.
     */
    _startClock() {
        const base = this.state.data.minutes_of_day;
        if (typeof base !== "number") {
            return;
        }
        const startedAt = Date.now();
        const tick = () => {
            const elapsed = Math.floor((Date.now() - startedAt) / 60000);
            const minutes = (base + elapsed) % 1440;
            const hh = String(Math.floor(minutes / 60)).padStart(2, "0");
            const mm = String(minutes % 60).padStart(2, "0");
            this.state.clock = `${hh}:${mm}`;
        };
        tick();
        this._clockTimer = setInterval(tick, 15000);
    }

    _stopClock() {
        if (this._clockTimer) {
            clearInterval(this._clockTimer);
            this._clockTimer = null;
        }
    }

    get apps() {
        const query = this.state.query.trim().toLowerCase();
        return this.menuService
            .getApps()
            .filter((app) => app.actionID)
            .map((app) => ({
                id: app.id,
                name: app.name,
                xmlid: app.xmlid,
                icon: hasRealIcon(app) ? app.webIconData : false,
                monogram: monogramFor(app.name),
                tint: tintFor(app),
            }))
            .filter((app) => !query || app.name.toLowerCase().includes(query));
    }

    get stats() {
        return this.state.data.stats || [];
    }

    /** Decided: live data, column hidden when there is none. */
    get hasStats() {
        return this.stats.length > 0;
    }

    openApp(app) {
        this.menuService.selectMenu(app.id);
    }

    onSearchKeydown(ev) {
        if (ev.key === "Enter") {
            const matches = this.apps;
            if (matches.length === 1) {
                this.openApp(matches[0]);
            }
        } else if (ev.key === "Escape") {
            this.state.query = "";
        }
    }
}

registry.category("actions").add("hospitality_home", HospitalityHome);
