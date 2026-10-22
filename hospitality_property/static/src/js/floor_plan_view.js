/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onMounted, useRef, onWillUnmount } from "@odoo/owl";

// ---------------------------------------------------------------------------
//  Constants
// ---------------------------------------------------------------------------
const STATUS_COLOR = {
    vacant_clean:   "#28a745",
    inspected:      "#20c997",
    vacant_dirty:   "#fd7e14",
    pickup:         "#ffc107",
    occupied_clean: "#007bff",
    occupied_dirty: "#17a2b8",
    ooo:            "#6c757d",
    oos:            "#dc3545",
};

const STATUS_LABELS = {
    vacant_clean:   "Vacant Clean",
    vacant_dirty:   "Vacant Dirty",
    occupied_clean: "Occupied Clean",
    occupied_dirty: "Occupied Dirty",
    inspected:      "Inspected",
    pickup:         "Pickup",
    ooo:            "Out of Order",
    oos:            "Out of Service",
};

// ---------------------------------------------------------------------------
//  FloorPlanView — registered as a client action component
// ---------------------------------------------------------------------------
export class FloorPlanView extends Component {
    static template = "hospitality_property.FloorPlanView";
    static props = {
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            floors: [],
            selectedIds: new Set(),
            filterStatus: "",
            filterFeature: "",
            filterFloor: "",
            allFeatures: [],
            loading: true,
        });

        this.dragStart = null;
        this.containerRef = useRef("container");
        this.lastClickedId = undefined;

        onMounted(() => {
            this._loadData();
            // Add global event listeners for drag
            document.addEventListener("mouseup", this.onMouseUp.bind(this));
        });

        onWillUnmount(() => {
            // Clean up event listeners
            document.removeEventListener("mouseup", this.onMouseUp.bind(this));
        });
    }

    // -----------------------------------------------------------------------
    //  Data loading
    // -----------------------------------------------------------------------
    async _loadData() {
        this.state.loading = true;
        try {
            const spaces = await this.orm.searchRead(
                "hospitality.space",
                [],
                ["id", "name", "code", "status", "floor_id",
                 "space_type_id", "feature_ids", "color"],
                { order: "floor_id asc, code asc" }
            );

            const features = await this.orm.searchRead(
                "hospitality.space.feature",
                [],
                ["id", "name"],
                { order: "sequence asc" }
            );
            this.state.allFeatures = features;

            const floorMap = {};
            for (const space of spaces) {
                const floorId = space.floor_id ? space.floor_id[0] : 0;
                const floorName = space.floor_id ? space.floor_id[1] : "No Floor";
                if (!floorMap[floorId]) {
                    floorMap[floorId] = { id: floorId, name: floorName, spaces: [] };
                }
                floorMap[floorId].spaces.push(space);
            }
            this.state.floors = Object.values(floorMap).sort(
                (a, b) => String(a.name).localeCompare(String(b.name))
            );
        } catch (error) {
            console.error("Error loading floor plan data:", error);
            this.notification.add("Error loading floor plan data", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    // -----------------------------------------------------------------------
    //  Filters
    // -----------------------------------------------------------------------
    get filteredFloors() {
        return this.state.floors
            .filter(f => !this.state.filterFloor ||
                         String(f.id) === String(this.state.filterFloor))
            .map(f => ({
                ...f,
                spaces: f.spaces.filter(s => this._spaceMatchesFilter(s)),
            }))
            .filter(f => f.spaces.length > 0);
    }

    _spaceMatchesFilter(space) {
        if (this.state.filterStatus && space.status !== this.state.filterStatus) {
            return false;
        }
        if (this.state.filterFeature) {
            const featureId = parseInt(this.state.filterFeature);
            if (!space.feature_ids || !space.feature_ids.includes(featureId)) {
                return false;
            }
        }
        return true;
    }

    onFilterStatus(ev)  { this.state.filterStatus  = ev.target.value; }
    onFilterFeature(ev) { this.state.filterFeature = ev.target.value; }
    onFilterFloor(ev)   { this.state.filterFloor   = ev.target.value; }

    // -----------------------------------------------------------------------
    //  Selection - FIX: Use arrow function to preserve 'this' context
    // -----------------------------------------------------------------------
    onCardClick = (space, ev) => {
        ev.stopPropagation();

        if (ev.shiftKey && this.lastClickedId !== undefined) {
            const allSpaces = this.filteredFloors.flatMap(f => f.spaces);
            const ids = allSpaces.map(s => s.id);
            const a = ids.indexOf(this.lastClickedId);
            const b = ids.indexOf(space.id);

            if (a !== -1 && b !== -1) {
                const [lo, hi] = a < b ? [a, b] : [b, a];
                const next = new Set(this.state.selectedIds);
                for (let i = lo; i <= hi; i++) {
                    next.add(ids[i]);
                }
                this.state.selectedIds = next;
            }
        } else {
            const next = new Set(this.state.selectedIds);
            if (next.has(space.id)) {
                next.delete(space.id);
            } else {
                next.add(space.id);
            }
            this.state.selectedIds = next;
            this.lastClickedId = space.id;
        }
    }

    isSelected(spaceId) {
        return this.state.selectedIds.has(spaceId);
    }

    get selectedCount() {
        return this.state.selectedIds.size;
    }

    clearSelection = () => {
        this.state.selectedIds = new Set();
        this.lastClickedId = undefined;
    }

    // -----------------------------------------------------------------------
    //  Drag select
    // -----------------------------------------------------------------------
    onMouseDown = (ev) => {
        if (ev.target.closest(".o_floor_space_card")) return;
        this.dragStart = { x: ev.clientX, y: ev.clientY };
        ev.preventDefault();
    }

    onMouseUp = (ev) => {
        if (this.dragStart) {
            this.dragStart = null;
            const el = this.containerRef.el;
            if (el) {
                const overlay = el.querySelector(".o_drag_overlay");
                if (overlay) overlay.remove();
            }
        }
    }

    onMouseMove = (ev) => {
        if (!this.dragStart) return;
        const container = this.containerRef.el;
        if (!container) return;

        let overlay = container.querySelector(".o_drag_overlay");
        if (!overlay) {
            overlay = document.createElement("div");
            overlay.className = "o_drag_overlay";
            container.style.position = "relative";
            container.appendChild(overlay);
        }

        const rect = container.getBoundingClientRect();
        const left = Math.min(this.dragStart.x, ev.clientX) - rect.left;
        const top = Math.min(this.dragStart.y, ev.clientY) - rect.top;
        const width = Math.abs(ev.clientX - this.dragStart.x);
        const height = Math.abs(ev.clientY - this.dragStart.y);

        Object.assign(overlay.style, {
            left: left + "px",
            top: top + "px",
            width: width + "px",
            height: height + "px",
        });

        const selRect = {
            left:   Math.min(this.dragStart.x, ev.clientX),
            right:  Math.max(this.dragStart.x, ev.clientX),
            top:    Math.min(this.dragStart.y, ev.clientY),
            bottom: Math.max(this.dragStart.y, ev.clientY),
        };

        const next = new Set();
        container.querySelectorAll(".o_floor_space_card").forEach(card => {
            const cr = card.getBoundingClientRect();
            const overlaps = !(
                cr.right  < selRect.left  ||
                cr.left   > selRect.right ||
                cr.bottom < selRect.top   ||
                cr.top    > selRect.bottom
            );
            if (overlaps) {
                const spaceId = parseInt(card.dataset.spaceId);
                if (!isNaN(spaceId)) {
                    next.add(spaceId);
                }
            }
        });
        this.state.selectedIds = next;
    }

    // -----------------------------------------------------------------------
    //  Bulk actions
    // -----------------------------------------------------------------------
    onBulkOOO = async () => {
        await this._openWizard("ooo");
    }

    onBulkOOS = async () => {
        await this._openWizard("oos");
    }

    onBulkVacantClean = async () => {
        if (!this.state.selectedIds.size) {
            this.notification.add("Please select at least one space", { type: "warning" });
            return;
        }
        try {
            await this.orm.call(
                "hospitality.space",
                "action_set_vacant_clean",
                [[...this.state.selectedIds]]
            );
            this.notification.add("Spaces set to Vacant Clean", { type: "success" });
            this.clearSelection();
            await this._loadData();
        } catch (error) {
            console.error("Error setting vacant clean:", error);
            this.notification.add(error.message || "Error updating spaces", { type: "danger" });
        }
    }

    async _openWizard(mode) {
        if (!this.state.selectedIds.size) {
            this.notification.add("Please select at least one space", { type: "warning" });
            return;
        }

        try {
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                name: mode === "ooo" ? "Set Out of Order" : "Set Out of Service",
                res_model: "hospitality.space.status.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_space_ids: [[6, 0, [...this.state.selectedIds]]],
                    default_mode: mode,
                },
            }, {
                onClose: async () => {
                    this.clearSelection();
                    await this._loadData();
                }
            });
        } catch (error) {
            console.error("Error opening wizard:", error);
            this.notification.add("Error opening wizard", { type: "danger" });
        }
    }

    // -----------------------------------------------------------------------
    //  Template helpers
    // -----------------------------------------------------------------------
    statusColor(status) {
        return STATUS_COLOR[status] || "#aaa";
    }

    statusLabel(status) {
        return STATUS_LABELS[status] || status;
    }

    get statusOptions() {
        return Object.entries(STATUS_LABELS).map(([k, v]) => ({
            value: k,
            label: v
        }));
    }
}

// ---------------------------------------------------------------------------
//  Register as a CLIENT ACTION — tag must match floor_plan_action.xml
// ---------------------------------------------------------------------------
registry.category("actions").add("hospitality_floor_plan", FloorPlanView);