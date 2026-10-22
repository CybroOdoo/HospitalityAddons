/** @odoo-module **/
import { Component, useState, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────

const DAY_WIDTH = 56; // px per date column
const ROW_HEIGHT = 40; // px per space row
const HEADER_HEIGHT = 56; // px for the date header row

const RANGE_OPTIONS = [7, 14, 30, 60];

const STATE_COLORS = {
    option: "yellow",
    confirmed: "blue",
    checked_in: "green",
    checked_out: "grey",
    no_show: "red",
    cancelled: "stripe-red",
};

const STATE_LABELS = {
    draft: "Draft",
    option: "Option",
    confirmed: "Confirmed",
    checked_in: "Checked In",
    checked_out: "Checked Out",
    no_show: "No Show",
    cancelled: "Cancelled",
};

/** Parse an 'YYYY-MM-DD' string into a local Date (midnight). */
function parseDate(str) {
    const [y, m, d] = str.split("-").map(Number);
    return new Date(y, m - 1, d);
}

/** Format a Date as 'YYYY-MM-DD'. */
function formatDate(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
}

function addDays(date, days) {
    const result = new Date(date);
    result.setDate(result.getDate() + days);
    return result;
}

function daysBetween(a, b) {
    const msPerDay = 24 * 60 * 60 * 1000;
    return Math.round((b - a) / msPerDay);
}

// ─────────────────────────────────────────────────────────────────────────
// TapeChartView Component
// ─────────────────────────────────────────────────────────────────────────

export class TapeChartView extends Component {
    static template = "hospitality_reservation.TapeChartView";
    // Permissive props: this component is mounted two ways —
    // (1) as a Controller via the "views" registry (gets the full
    //     standardViewProps contract from the View loader), and
    // (2) directly by an ir.actions.client wrapper (gets only
    //     `action`/`context`), since act_window does not accept
    //     custom view types outside the core Selection on ir.ui.view.
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.rootRef = useRef("tapeChartRoot");
        this.gridRef = useRef("tapeChartGrid");

        this.dayWidth = DAY_WIDTH;
        this.rowHeight = ROW_HEIGHT;
        this.headerHeight = HEADER_HEIGHT;
        this.rangeOptions = RANGE_OPTIONS;
        this.stateColors = STATE_COLORS;
        this.stateLabels = STATE_LABELS;

        // context may come from standardViewProps (Controller mount) or
        // from action.context (client-action mount) — normalize here.
        const context = this.props.context || (this.props.action && this.props.action.context) || {};

        this.state = useState({
            propertyId: context.default_property_id || false,
            properties: [],
            dateFrom: this._defaultDateFrom(),
            rangeDays: 14,
            viewMode: "space", // "space" | "space_type"
            spaces: [],
            spaceTypes: [],
            reservations: [],
            oooBlocks: [],
            isLoading: true,
            filters: {
                state: false,
                sourceCodeId: false,
                marketSegmentId: false,
            },
            sourceCodes: [],
            marketSegments: [],
        });

        // Drag interaction state (not reactive — perf-sensitive, mutated
        // directly during pointermove and only synced to `state` on drop).
        this.drag = null;

        onWillStart(async () => {
            await this._loadProperties();
            await this._loadFilterOptions();
            await this._loadData();
        });

        onMounted(() => {
            this._attachPointerListeners();
        });

        onWillUnmount(() => {
            this._detachPointerListeners();
        });
    }

    // ─────────────────────────────────────────────────────────────────
    // Date window helpers
    // ─────────────────────────────────────────────────────────────────

    _defaultDateFrom() {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return formatDate(today);
    }

    get dateFromObj() {
        return parseDate(this.state.dateFrom);
    }

    get dateToObj() {
        return addDays(this.dateFromObj, this.state.rangeDays);
    }

    get dateTo() {
        return formatDate(this.dateToObj);
    }

    /** Array of Date objects, one per visible day, for the header row. */
    get dateColumns() {
        const cols = [];
        for (let i = 0; i < this.state.rangeDays; i++) {
            cols.push(addDays(this.dateFromObj, i));
        }
        return cols;
    }

    // ─────────────────────────────────────────────────────────────────
    // Data loading
    // ─────────────────────────────────────────────────────────────────

    async _loadProperties() {
        const properties = await this.orm.searchRead(
            "hospitality.property",
            [],
            ["id", "name"]
        );
        this.state.properties = properties;
        if (!this.state.propertyId && properties.length) {
            this.state.propertyId = await this._defaultPropertyId(properties);
        }
    }

    /**
     * Pick the property to show on first load when nothing was supplied
     * via context (default_property_id). Resolved server-side, where
     * the current user is unambiguous, rather than guessed from
     * client-side session globals. Falls back to the first property in
     * the already-loaded list if the RPC fails or returns nothing
     * usable, so the chart still renders something rather than nothing.
     */
    async _defaultPropertyId(properties) {
        try {
            const defaultId = await this.orm.call(
                "hospitality.reservation",
                "get_default_tape_chart_property_id",
                []
            );
            if (defaultId && properties.some((p) => p.id === defaultId)) {
                return defaultId;
            }
        } catch {
            // fall through to the first available property below.
        }
        return properties[0].id;
    }

    async _loadFilterOptions() {
        try {
            this.state.sourceCodes = await this.orm.searchRead(
                "hospitality.source.code",
                [],
                ["id", "name"]
            );
        } catch {
            this.state.sourceCodes = [];
        }
        try {
            this.state.marketSegments = await this.orm.searchRead(
                "hospitality.market.segment",
                [],
                ["id", "name"]
            );
        } catch {
            this.state.marketSegments = [];
        }
    }

    async _loadData() {
        if (!this.state.propertyId) {
            this.state.spaces = [];
            this.state.reservations = [];
            this.state.oooBlocks = [];
            this.state.isLoading = false;
            return;
        }
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "hospitality.reservation",
                "get_tape_chart_data",
                [this.state.propertyId, this.state.dateFrom, this.dateTo]
            );
            this.state.spaces = data.spaces || [];
            this.state.spaceTypes = data.space_types || [];
            this.state.reservations = data.reservations || [];
            this.state.oooBlocks = data.ooo_blocks || [];
        } finally {
            this.state.isLoading = false;
        }
    }

    async reload() {
        await this._loadData();
    }

    // ─────────────────────────────────────────────────────────────────
    // Filtering / row computation
    // ─────────────────────────────────────────────────────────────────

    get filteredReservations() {
        return this.state.reservations.filter((r) => {
            if (this.state.filters.state && r.state !== this.state.filters.state) {
                return false;
            }
            if (
                this.state.filters.sourceCodeId &&
                r.source_code_id !== this.state.filters.sourceCodeId
            ) {
                return false;
            }
            if (
                this.state.filters.marketSegmentId &&
                r.market_segment_id !== this.state.filters.marketSegmentId
            ) {
                return false;
            }
            return true;
        });
    }

    /** Rows to render: either one per space, or one per space_type (aggregated). */
    get rows() {
        if (this.state.viewMode === "space_type") {
            return this.state.spaceTypes.map((st) => ({
                id: `st_${st.id}`,
                spaceTypeId: st.id,
                label: `${st.name} (${st.space_count})`,
                isAggregate: true,
            }));
        }
        return this.state.spaces.map((sp) => ({
            id: `sp_${sp.id}`,
            spaceId: sp.id,
            spaceTypeId: sp.space_type_id,
            label: sp.name,
            stateClass: sp.state,
            isAggregate: false,
        }));
    }

    /** Reservation bars positioned for a given row. */
    barsForRow(row) {
        const reservations = this.filteredReservations.filter((r) => {
            if (row.isAggregate) {
                return r.space_type_id === row.spaceTypeId;
            }
            return r.space_id === row.spaceId;
        });
        return reservations.map((r) => this._barGeometry(r));
    }

    oooBlocksForRow(row) {
        if (row.isAggregate) {
            return [];
        }
        return this.state.oooBlocks
            .filter((b) => b.space_id === row.spaceId)
            .map((b) => this._oooGeometry(b));
    }

    /** Compute left/width in px (and clamp to visible window) for a reservation. */
    _barGeometry(reservation) {
        const arrival = parseDate(reservation.arrival);
        const departure = parseDate(reservation.departure);
        const visibleFrom = this.dateFromObj;
        const visibleTo = this.dateToObj;

        const clampedStart = arrival < visibleFrom ? visibleFrom : arrival;
        const clampedEnd = departure > visibleTo ? visibleTo : departure;

        const left = daysBetween(visibleFrom, clampedStart) * this.dayWidth;
        const width = Math.max(
            daysBetween(clampedStart, clampedEnd) * this.dayWidth,
            this.dayWidth / 2
        );

        return {
            reservation,
            left,
            width,
            colorClass: `o_tape_bar_${this.stateColors[reservation.state] || "default"}`,
            label: `${reservation.partner_name} — ${reservation.name}`,
        };
    }

    _oooGeometry(block) {
        const from = parseDate(block.date_from);
        const to = parseDate(block.date_to);
        const visibleFrom = this.dateFromObj;
        const left = daysBetween(visibleFrom, from) * this.dayWidth;
        const width = daysBetween(from, to) * this.dayWidth;
        return { block, left, width };
    }

    // ─────────────────────────────────────────────────────────────────
    // Date navigation
    // ─────────────────────────────────────────────────────────────────

    onClickPrev() {
        this.state.dateFrom = formatDate(
            addDays(this.dateFromObj, -this.state.rangeDays)
        );
        this.reload();
    }

    onClickNext() {
        this.state.dateFrom = formatDate(
            addDays(this.dateFromObj, this.state.rangeDays)
        );
        this.reload();
    }

    onClickToday() {
        this.state.dateFrom = this._defaultDateFrom();
        this.reload();
    }

    onChangeRange(ev) {
        this.state.rangeDays = parseInt(ev.target.value, 10);
        this.reload();
    }

    onChangeProperty(ev) {
        this.state.propertyId = parseInt(ev.target.value, 10);
        this.reload();
    }

    onChangeViewMode(ev) {
        this.state.viewMode = ev.target.value;
    }

    onChangeFilter(key, ev) {
        const value = ev.target.value;
        this.state.filters[key] = value ? parseInt(value, 10) || value : false;
    }

    // ─────────────────────────────────────────────────────────────────
    // Click → open in side panel (form view)
    // ─────────────────────────────────────────────────────────────────

    async onClickBar(reservation, ev) {
        if (this.drag && this.drag.moved) {
            // Suppress click-open if this was actually a drag release.
            return;
        }
        ev.stopPropagation();
        await this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "hospitality.reservation",
                res_id: reservation.id,
                views: [[false, "form"]],
                target: "new",
            },
            {
                onClose: () => this.reload(),
            }
        );
    }

    /** Drag on an empty cell range → open new reservation form pre-filled. */
    async _openNewReservation({ spaceId, spaceTypeId, dateFrom, dateTo }) {
        const context = {
            default_property_id: this.state.propertyId,
            default_space_id: spaceId || false,
            default_space_type_id: spaceTypeId || false,
            default_arrival: dateFrom,
            default_departure: dateTo,
        };
        await this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "hospitality.reservation",
                views: [[false, "form"]],
                target: "new",
                context,
            },
            {
                onClose: () => this.reload(),
            }
        );
    }

    // ─────────────────────────────────────────────────────────────────
    // Pointer-based drag interactions
    //
    // We use pointer events (not native HTML5 DnD) since the chart needs
    // fine-grained control over snapping to day columns, distinguishing
    // horizontal (extend/shrink) vs vertical (move) drags, and rendering
    // a live ghost bar — none of which native DnD handles well.
    // ─────────────────────────────────────────────────────────────────

    _attachPointerListeners() {
        this._onPointerMove = this._handlePointerMove.bind(this);
        this._onPointerUp = this._handlePointerUp.bind(this);
        window.addEventListener("pointermove", this._onPointerMove);
        window.addEventListener("pointerup", this._onPointerUp);
    }

    _detachPointerListeners() {
        window.removeEventListener("pointermove", this._onPointerMove);
        window.removeEventListener("pointerup", this._onPointerUp);
    }

    /** mousedown/pointerdown on an empty grid cell → start "create" drag. */
    onPointerDownCell(row, dayIndex, ev) {
        if (ev.button !== 0 || row.isAggregate) {
            return;
        }
        ev.preventDefault();
        this.drag = {
            type: "create",
            row,
            startDayIndex: dayIndex,
            currentDayIndex: dayIndex,
            startY: ev.clientY,
            moved: false,
        };
    }

    /** pointerdown on an existing bar edge → start "resize" drag. */
    onPointerDownBarEdge(reservation, edge, ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const arrival = parseDate(reservation.arrival);
        const departure = parseDate(reservation.departure);
        this.drag = {
            type: "resize",
            edge, // "start" | "end"
            reservation,
            originalArrival: arrival,
            originalDeparture: departure,
            deltaDays: 0,
            startX: ev.clientX,
            moved: false,
        };
    }

    /** pointerdown on bar body → start "move" drag (horizontal = extend whole bar, vertical = change space). */
    onPointerDownBarBody(reservation, ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const arrival = parseDate(reservation.arrival);
        const departure = parseDate(reservation.departure);
        this.drag = {
            type: "move",
            reservation,
            originalArrival: arrival,
            originalDeparture: departure,
            originalSpaceId: reservation.space_id,
            deltaDays: 0,
            deltaRows: 0,
            startX: ev.clientX,
            startY: ev.clientY,
            moved: false,
        };
    }

    _handlePointerMove(ev) {
        if (!this.drag) {
            return;
        }
        this.drag.moved = true;

        if (this.drag.type === "create") {
            const grid = this.gridRef.el;
            if (!grid) return;
            const rect = grid.getBoundingClientRect();
            const x = ev.clientX - rect.left + grid.scrollLeft;
            const dayIndex = Math.max(
                0,
                Math.min(
                    this.state.rangeDays - 1,
                    Math.floor(x / this.dayWidth)
                )
            );
            this.drag.currentDayIndex = dayIndex;
            this._renderGhost();
        } else if (this.drag.type === "resize") {
            const deltaPx = ev.clientX - this.drag.startX;
            this.drag.deltaDays = Math.round(deltaPx / this.dayWidth);
            this._renderGhost();
        } else if (this.drag.type === "move") {
            const deltaPxX = ev.clientX - this.drag.startX;
            const deltaPxY = ev.clientY - this.drag.startY;
            this.drag.deltaDays = Math.round(deltaPxX / this.dayWidth);
            this.drag.deltaRows = Math.round(deltaPxY / this.rowHeight);
            this._renderGhost();
        }
    }

    /**
     * Ghost bar rendering is done via direct DOM style mutation on a
     * dedicated overlay element (ref="dragGhost") rather than OWL state,
     * to avoid re-rendering the whole grid on every pointermove (perf:
     * grid can hold 50 rows × 14-60 cols × up to 200 bars).
     */
    _renderGhost() {
        const ghostEl = this.rootRef.el && this.rootRef.el.querySelector(".o_tape_drag_ghost");
        if (!ghostEl || !this.drag) {
            return;
        }
        ghostEl.style.display = "block";

        if (this.drag.type === "create") {
            const { row, startDayIndex, currentDayIndex } = this.drag;
            const lo = Math.min(startDayIndex, currentDayIndex);
            const hi = Math.max(startDayIndex, currentDayIndex);
            const rowIndex = this.rows.findIndex((r) => r.id === row.id);
            ghostEl.style.left = `${lo * this.dayWidth}px`;
            ghostEl.style.width = `${(hi - lo + 1) * this.dayWidth}px`;
            ghostEl.style.top = `${rowIndex * this.rowHeight}px`;
            ghostEl.style.height = `${this.rowHeight}px`;
        } else if (this.drag.type === "resize") {
            const bar = this._barGeometry(this.drag.reservation);
            const rowIndex = this.rows.findIndex(
                (r) => !r.isAggregate && r.spaceId === this.drag.reservation.space_id
            );
            let left = bar.left;
            let width = bar.width;
            if (this.drag.edge === "start") {
                left = bar.left + this.drag.deltaDays * this.dayWidth;
                width = bar.width - this.drag.deltaDays * this.dayWidth;
            } else {
                width = bar.width + this.drag.deltaDays * this.dayWidth;
            }
            ghostEl.style.left = `${left}px`;
            ghostEl.style.width = `${Math.max(width, this.dayWidth / 2)}px`;
            ghostEl.style.top = `${rowIndex * this.rowHeight}px`;
            ghostEl.style.height = `${this.rowHeight}px`;
        } else if (this.drag.type === "move") {
            const bar = this._barGeometry(this.drag.reservation);
            const rowIndex = this.rows.findIndex(
                (r) => !r.isAggregate && r.spaceId === this.drag.reservation.space_id
            );
            const newRowIndex = Math.max(
                0,
                Math.min(this.rows.length - 1, rowIndex + this.drag.deltaRows)
            );
            ghostEl.style.left = `${bar.left + this.drag.deltaDays * this.dayWidth}px`;
            ghostEl.style.width = `${bar.width}px`;
            ghostEl.style.top = `${newRowIndex * this.rowHeight}px`;
            ghostEl.style.height = `${this.rowHeight}px`;
        }
    }

    _hideGhost() {
        const ghostEl = this.rootRef.el && this.rootRef.el.querySelector(".o_tape_drag_ghost");
        if (ghostEl) {
            ghostEl.style.display = "none";
        }
    }

    async _handlePointerUp() {
        if (!this.drag) {
            return;
        }
        const drag = this.drag;
        this.drag = null;
        this._hideGhost();

        if (!drag.moved) {
            return; // plain click, handled by onClickBar / nothing for cells
        }

        try {
            if (drag.type === "create") {
                await this._commitCreate(drag);
            } else if (drag.type === "resize") {
                await this._commitResize(drag);
            } else if (drag.type === "move") {
                await this._commitMove(drag);
            }
        } catch (e) {
            this.notification.add(
                e.message || e.data?.message || "Could not save the change.",
                { type: "danger" }
            );
            await this.reload();
        }
    }

    async _commitCreate(drag) {
        const { row, startDayIndex, currentDayIndex } = drag;
        const lo = Math.min(startDayIndex, currentDayIndex);
        const hi = Math.max(startDayIndex, currentDayIndex);
        const dateFrom = formatDate(addDays(this.dateFromObj, lo));
        const dateTo = formatDate(addDays(this.dateFromObj, hi + 1));

        await this._openNewReservation({
            spaceId: row.isAggregate ? false : row.spaceId,
            spaceTypeId: row.spaceTypeId,
            dateFrom,
            dateTo,
        });
    }

    /** Drag bar horizontally (resize from an edge) → extend/shrink: write on reservation. */
    async _commitResize(drag) {
        if (drag.deltaDays === 0) {
            return;
        }
        const { reservation, originalArrival, originalDeparture, edge, deltaDays } = drag;
        let newArrival = originalArrival;
        let newDeparture = originalDeparture;
        if (edge === "start") {
            newArrival = addDays(originalArrival, deltaDays);
        } else {
            newDeparture = addDays(originalDeparture, deltaDays);
        }
        if (newDeparture <= newArrival) {
            this.notification.add("Departure must be after arrival.", { type: "warning" });
            await this.reload();
            return;
        }
        await this.orm.write("hospitality.reservation", [reservation.id], {
            arrival: formatDate(newArrival),
            departure: formatDate(newDeparture),
        });
        this.notification.add("Reservation dates updated.", { type: "success" });
        await this.reload();
    }

    /**
     * Drag bar: horizontal component moves dates (whole-bar shift),
     * vertical component moves to another space.
     *   - state == checked_in → open move wizard (manual re-assignment
     *     while guest is in-house has billing/housekeeping implications).
     *   - otherwise → direct write on space_id (and arrival/departure if
     *     also shifted horizontally).
     */
    async _commitMove(drag) {
        const { reservation, originalArrival, originalDeparture, deltaDays, deltaRows } = drag;
        if (deltaDays === 0 && deltaRows === 0) {
            return;
        }

        const vals = {};
        if (deltaDays !== 0) {
            vals.arrival = formatDate(addDays(originalArrival, deltaDays));
            vals.departure = formatDate(addDays(originalDeparture, deltaDays));
        }

        let newSpaceId = reservation.space_id;
        if (deltaRows !== 0) {
            const rows = this.rows.filter((r) => !r.isAggregate);
            const currentIndex = rows.findIndex((r) => r.spaceId === reservation.space_id);
            const targetIndex = Math.max(
                0,
                Math.min(rows.length - 1, currentIndex + deltaRows)
            );
            const targetRow = rows[targetIndex];
            if (targetRow && targetRow.spaceId !== reservation.space_id) {
                newSpaceId = targetRow.spaceId;
            }
        }

        if (newSpaceId !== reservation.space_id) {
            if (reservation.state === "checked_in") {
                await this._openMoveWizard(reservation, newSpaceId, vals);
                return;
            }
            vals.space_id = newSpaceId;
        }

        if (!Object.keys(vals).length) {
            return;
        }

        await this.orm.write("hospitality.reservation", [reservation.id], vals);
        this.notification.add("Reservation updated.", { type: "success" });
        await this.reload();
    }

    /** state == checked_in and moving space → route through the move/room-change wizard. */
    async _openMoveWizard(reservation, newSpaceId, extraVals) {
        await this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "hospitality.reservation.move.wizard",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_reservation_id: reservation.id,
                    default_new_space_id: newSpaceId,
                    default_new_arrival: extraVals.arrival || reservation.arrival,
                    default_new_departure: extraVals.departure || reservation.departure,
                },
            },
            {
                onClose: () => this.reload(),
            }
        );
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Registration
//
// Odoo 19's ir.ui.view.type field is a hardcoded Selection that rejects
// unknown values, and ir.actions.act_window's view_mode resolution only
// recognises core view types — so a genuinely custom view type like
// "tape_chart" cannot be wired through act_window/ir.ui.view. Instead we
// register TapeChartView as the component of a plain ir.actions.client,
// which mounts it directly with no view-type validation involved.
// ─────────────────────────────────────────────────────────────────────────

registry.category("actions").add("hospitality_tape_chart", TapeChartView);