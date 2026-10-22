/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * FD-06 — Front Desk Dashboard.
 *
 * Pulls all counters in a single RPC to
 * `hospitality.front.desk.shift.get_dashboard_data` and renders the
 * arrivals / in-house / departures queues, available rooms by type,
 * occupancy gauge, outstanding AR, and open FD shifts.
 */
export class FrontDeskDashboard extends Component {
    static template = "hospitality_front_desk.FrontDeskDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            propertyId: false,
            properties: [],
            data: {
                arrivals_count: 0,
                in_house_count: 0,
                departures_count: 0,
                available_by_type: [],
                occupancy_pct: 0,
                outstanding_ar_count: 0,
                open_shifts: [],
            },
        });

        onWillStart(async () => {
            await this._loadProperties();
            await this._loadDashboard();
        });
    }

    async _loadProperties() {
        const properties = await this.orm.searchRead(
            "hospitality.property",
            [],
            ["id", "name"]
        );
        this.state.properties = properties;
        if (properties.length) {
            this.state.propertyId = properties[0].id;
        }
    }

    async _loadDashboard() {
        if (!this.state.propertyId) {
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        const data = await this.orm.call(
            "hospitality.front.desk.shift",
            "get_dashboard_data",
            [this.state.propertyId]
        );
        this.state.data = data;
        this.state.loading = false;
    }

    async onPropertyChange(ev) {
        this.state.propertyId = parseInt(ev.target.value, 10);
        await this._loadDashboard();
    }

    async onRefresh() {
        await this._loadDashboard();
    }

    _openList(resModel, domain, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: resModel,
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    onOpenArrivals() {
        this._openList(
            "hospitality.reservation",
            [
                ["property_id", "=", this.state.propertyId],
                ["arrival", "=", this.state.data.date],
                ["state", "=", "confirmed"],
            ],
            "Arrivals"
        );
    }

    onOpenInHouse() {
        this._openList(
            "hospitality.reservation",
            [
                ["property_id", "=", this.state.propertyId],
                ["state", "=", "checked_in"],
            ],
            "In-House"
        );
    }

    onOpenDepartures() {
        this._openList(
            "hospitality.reservation",
            [
                ["property_id", "=", this.state.propertyId],
                ["departure", "=", this.state.data.date],
                ["state", "=", "checked_in"],
            ],
            "Departures"
        );
    }

    onOpenAr() {
        this._openList(
            "hospitality.ar.account",
            [
                ["property_id", "=", this.state.propertyId],
                ["balance", "!=", 0],
            ],
            "Outstanding AR"
        );
    }
}

registry.category("actions").add("hospitality_front_desk.fd_dashboard", FrontDeskDashboard);