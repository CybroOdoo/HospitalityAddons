/** @odoo-module **/
// ---------------------------------------------------------------------------
//  Hospitality — Property Switcher (Systray)
//  Odoo 19 — uses dedicated controller endpoints
// ---------------------------------------------------------------------------

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

export class PropertySwitcher extends Component {
    static template = "hospitality_base.PropertySwitcher";
    static props = {};

    setup() {
        this.notification = useService("notification");

        this.state = useState({
            isOpen: false,
            currentProperty: null,
            properties: [],
        });

        onWillStart(async () => {
            await this._loadProperties();
        });
    }

    async _loadProperties() {
        try {
            const data = await rpc("/hospitality/property_data", {});
            if (!data) return;

            this.state.properties = data.properties || [];

            if (data.current_property_id) {
                this.state.currentProperty =
                    this.state.properties.find(
                        (p) => p.id === data.current_property_id
                    ) || null;
            }
        } catch (e) {
            console.error("PropertySwitcher: failed to load properties", e);
        }
    }

    // NA-05 fix: these three handlers are converted from plain class
    // methods to arrow-function class fields. Plain methods lose their
    // `this` binding the moment they're passed by reference instead of
    // called as `component.method()` — e.g. `t-on-click="selectProperty(prop)"`
    // inside a t-foreach can compile to a call that no longer carries the
    // component as `this`, which is exactly what "Cannot read properties
    // of undefined (reading 'state')" means: `this` was undefined, so
    // `this.state` failed. Arrow-function fields close over `this`
    // lexically at construction time, so they stay correctly bound no
    // matter how the template invokes them — this fix holds regardless
    // of the exact t-on-click syntax used in property_switcher.xml,
    // which wasn't available to confirm the precise trigger.

    toggleDropdown = () => {
        this.state.isOpen = !this.state.isOpen;
    };

    closeDropdown = () => {
        this.state.isOpen = false;
    };

    selectProperty = async (property) => {
        if (!property) return;
        if (
            this.state.currentProperty &&
            property.id === this.state.currentProperty.id
        ) {
            this.state.isOpen = false;
            return;
        }
        try {
            const result = await rpc("/hospitality/switch_property", {
                property_id: property.id,
            });
            if (result && result.ok) {
                window.location.reload();
            } else {
                this.notification.add(
                    (result && result.error) || "Could not switch property.",
                    { type: "danger" }
                );
            }
        } catch (e) {
            this.notification.add(
                "Error switching property. Please try again.",
                { type: "danger" }
            );
        }
    };

    formatBusinessDate(dateStr) {
        if (!dateStr) return "";
        const [y, m, d] = dateStr.split("-");
        return `${d}/${m}/${y}`;
    }
}

// The property switcher is no longer mounted in the systray: the navbar
// carries the business-date pill from the backend theme and a second
// dropdown beside it read as clutter. The component is kept whole and
// exported, so putting it back anywhere is a one-line registration:
//
//   registry.category("systray").add("hospitality.property_switcher", {
//       Component: PropertySwitcher,
//       sequence: 5,
//   });
