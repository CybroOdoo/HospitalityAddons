/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * REP-03: Manager Flash — live front-desk/management dashboard.
 *
 * Single RPC (hospitality.kpi.daily.get_manager_flash_data) backs the
 * whole screen: headline KPIs + day-over-day deltas and flow counters
 * come from the latest two night-audit-materialized snapshots, while
 * in-house count/balance are computed live. See the Python method's
 * docstring for the full split.
 */
export class ManagerFlashDashboard extends Component {
    static template = "hospitality_reporting.ManagerFlashDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: false,
            data: null,
            properties: [],
        });

        onWillStart(async () => {
            await this.loadProperties();
            await this.loadData();
        });
    }

    async loadProperties() {
        try {
            this.state.properties = await this.orm.call(
                "hospitality.kpi.daily", "get_dashboard_properties", []
            );
        } catch {
            this.state.properties = [];
        }
    }

    async loadData(propertyId = false) {
        this.state.loading = true;
        this.state.error = false;
        try {
            this.state.data = await this.orm.call(
                "hospitality.kpi.daily", "get_manager_flash_data", [propertyId]
            );
        } catch (err) {
            this.state.error = (err && err.message && err.message.data
                && err.message.data.message) || (err && err.message) || String(err);
        } finally {
            this.state.loading = false;
        }
    }

    onPropertyChange(ev) {
        const propertyId = parseInt(ev.target.value, 10);
        this.loadData(propertyId || false);
    }

    onRefreshClick() {
        this.loadData(this.state.data && this.state.data.property_id);
    }

    // ── Formatting helpers (called from the template) ────────────────
    formatPct(value) {
        return `${((value || 0) * 100).toFixed(1)}%`;
    }

    formatAmount(value) {
        const symbol = (this.state.data && this.state.data.currency_symbol) || "";
        return `${symbol}${(value || 0).toFixed(2)}`;
    }

    formatDelta(value, { isPct = false } = {}) {
        const v = value || 0;
        const sign = v > 0 ? "+" : "";
        return isPct ? `${sign}${(v * 100).toFixed(1)} pts` : `${sign}${v.toFixed(2)}`;
    }

    deltaClass(value) {
        if (!value) {
            return "of-mf-delta-flat";
        }
        return value > 0 ? "of-mf-delta-up" : "of-mf-delta-down";
    }

    // ── Donut chart helpers ────────────────────────────────────────
    // Both mixes render as a CSS conic-gradient ring plus a text
    // legend, so no extra charting library is required.
    donutGradient(mix) {
        const total = (mix || []).reduce((sum, m) => sum + (m.value || 0), 0);
        if (!total) {
            return "background: var(--of-mf-donut-empty)";
        }
        let cumulative = 0;
        const stops = mix.map((m, idx) => {
            const start = (cumulative / total) * 100;
            cumulative += m.value;
            const end = (cumulative / total) * 100;
            return `var(--of-mf-color-${idx % 8}) ${start}% ${end}%`;
        });
        return `background: conic-gradient(${stops.join(", ")})`;
    }

    mixWithShare(mix) {
        const total = (mix || []).reduce((sum, m) => sum + (m.value || 0), 0) || 1;
        return (mix || []).map((m, idx) => ({
            ...m,
            share: `${((m.value / total) * 100).toFixed(1)}%`,
            colorIndex: idx % 8,
        }));
    }
}

registry.category("actions").add("hospitality_reporting.manager_flash", ManagerFlashDashboard);