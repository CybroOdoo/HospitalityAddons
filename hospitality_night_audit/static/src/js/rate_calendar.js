/** @odoo-module **/
/*
 * RATE-07 — Spreadsheet-style date × space_type rate calendar.
 */

import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const DATE_WINDOW_OPTIONS = [30, 60, 90, 365];

function fmtDate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
}

function addDays(d, n) {
    const r = new Date(d);
    r.setDate(r.getDate() + n);
    return r;
}

export class RateCalendarRenderer extends Component {
    static template = "hospitality_rate.RateCalendar";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        this.state = useState({
            rateCodes: [],
            spaceTypes: [],
            rateCodeId: false,
            propertyId: false,
            startDate: fmtDate(today),
            windowDays: 30,
            dates: [],
            cells: {},
            occupancy: { adults: 2, children: 0 },
            editingKey: null,
            editValue: "",
            minPrice: 0,
            maxPrice: 0,
            loading: true,
            savingKey: null,         // cell currently being saved
            justSavedKey: null,      // cell just saved (for flash)
            copyDialog: {
                open: false,
                srcFrom: "",
                srcTo: "",
                dstFrom: "",
                dstTo: "",
            },
        });

        this.inputRef = useRef("editInput");

        onWillStart(async () => {
            await this._loadRateCodes();
            if (this.state.rateCodeId) {
                await this._loadGrid();
            } else {
                this.state.loading = false;
            }
        });
    }

    // ──────────────────────────────────────────────────────────────────────
    // Data loading
    // ──────────────────────────────────────────────────────────────────────

    async _loadRateCodes() {
        const codes = await this.orm.searchRead(
            "hospitality.rate.code",
            [["state", "in", ["draft", "active"]]],
            ["id", "code", "name", "property_id"],
            { limit: 200 },
        );
        this.state.rateCodes = codes;
        if (codes.length) {
            this.state.rateCodeId = codes[0].id;
            this.state.propertyId = codes[0].property_id
                ? codes[0].property_id[0]
                : false;
        }
    }

    async _loadSpaceTypes() {
        const domain = this.state.propertyId
            ? [["property_id", "=", this.state.propertyId]]
            : [];
        this.state.spaceTypes = await this.orm.searchRead(
            "hospitality.space.type",
            domain,
            ["id", "name"],
            { limit: 100 },
        );
    }

    _computeDates() {
        const start = new Date(this.state.startDate);
        const dates = [];
        for (let i = 0; i < this.state.windowDays; i++) {
            dates.push(fmtDate(addDays(start, i)));
        }
        this.state.dates = dates;
    }

    async _loadPlans() {
        if (!this.state.rateCodeId || !this.state.dates.length) {
            this.state.cells = {};
            return;
        }
        const first = this.state.dates[0];
        const last = this.state.dates[this.state.dates.length - 1];
        const plans = await this.orm.searchRead(
            "hospitality.rate.plan",
            [
                ["rate_code_id", "=", this.state.rateCodeId],
                ["date_from", "<=", last],
                ["date_to", ">=", first],
            ],
            ["space_type_id", "date_from", "date_to",
             "price_double", "weekday_mask"],
            { limit: 5000 },
        );

        const cells = {};
        let minP = Infinity;
        let maxP = -Infinity;

        for (const p of plans) {
            const stId = p.space_type_id[0];
            const dFrom = new Date(p.date_from);
            const dTo = new Date(p.date_to);
            for (const ds of this.state.dates) {
                const d = new Date(ds);
                if (d >= dFrom && d <= dTo) {
                    const weekdayBit = (d.getDay() + 6) % 7;
                    if (p.weekday_mask & (1 << weekdayBit)) {
                        cells[`${stId}:${ds}`] = p.price_double;
                        if (p.price_double < minP) minP = p.price_double;
                        if (p.price_double > maxP) maxP = p.price_double;
                    }
                }
            }
        }
        this.state.cells = cells;
        this.state.minPrice = isFinite(minP) ? minP : 0;
        this.state.maxPrice = isFinite(maxP) ? maxP : 0;
    }

    async _loadGrid() {
        this.state.loading = true;
        try {
            this._computeDates();
            await this._loadSpaceTypes();
            await this._loadPlans();
        } finally {
            this.state.loading = false;
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    // Toolbar handlers
    // ──────────────────────────────────────────────────────────────────────

    async onRateCodeChange(ev) {
        const id = parseInt(ev.target.value, 10);
        this.state.rateCodeId = id;
        const rc = this.state.rateCodes.find((r) => r.id === id);
        this.state.propertyId = rc && rc.property_id ? rc.property_id[0] : false;
        await this._loadGrid();
    }

    async onWindowChange(ev) {
        this.state.windowDays = parseInt(ev.target.value, 10);
        await this._loadGrid();
    }

    async onStartDateChange(ev) {
        this.state.startDate = ev.target.value;
        await this._loadGrid();
    }

    onAdultsChange(ev) {
        this.state.occupancy.adults = parseInt(ev.target.value, 10) || 1;
    }

    onChildrenChange(ev) {
        this.state.occupancy.children = parseInt(ev.target.value, 10) || 0;
    }

    // ──────────────────────────────────────────────────────────────────────
    // Cell edit
    // ──────────────────────────────────────────────────────────────────────

    onCellClick(spaceTypeId, dateStr) {
        const key = `${spaceTypeId}:${dateStr}`;
        if (this.state.editingKey === key) return;
        this.state.editingKey = key;
        const current = this.state.cells[key];
        this.state.editValue = current != null ? String(current) : "";
        Promise.resolve().then(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
                this.inputRef.el.select();
            }
        });
    }

    onEditInput(ev) {
        this.state.editValue = ev.target.value;
    }

    async onEditBlur(spaceTypeId, dateStr) {
        const key = `${spaceTypeId}:${dateStr}`;
        if (this.state.editingKey !== key) return;
        await this._commitEdit(spaceTypeId, dateStr);
    }

    async onEditKeydown(ev, spaceTypeId, dateStr) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            await this._commitEdit(spaceTypeId, dateStr);
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.state.editingKey = null;
        }
    }

    async _commitEdit(spaceTypeId, dateStr) {
        const raw = this.state.editValue;
        const price = parseFloat(raw);
        this.state.editingKey = null;
        if (raw === "" || isNaN(price) || price < 0) {
            console.warn("Rate Calendar: invalid value, skipping save:", raw);
            return;
        }
        await this._writeCell(spaceTypeId, dateStr, price);
    }

    async _writeCell(spaceTypeId, dateStr, price) {
        const key = `${spaceTypeId}:${dateStr}`;
        this.state.savingKey = key;
        console.log("Rate Calendar: saving",
            { rateCodeId: this.state.rateCodeId, spaceTypeId, dateStr, price });
        try {
            const planId = await this.orm.call(
                "hospitality.rate.plan",
                "action_upsert_cell",
                [this.state.rateCodeId, spaceTypeId, dateStr, price],
            );
            this.state.cells[key] = price;
            this._recomputeMinMax();
            this.state.savingKey = null;
            this.state.justSavedKey = key;
            setTimeout(() => {
                if (this.state.justSavedKey === key) {
                    this.state.justSavedKey = null;
                }
            }, 1200);
            this.notification.add(
                _t("Saved %s", price.toFixed(2)),
                { type: "success", sticky: false },
            );
        } catch (err) {
            this.state.savingKey = null;
            console.error("Rate Calendar: save failed", err);
            this.notification.add(
                _t("Failed to save price (see console)"),
                { type: "danger" },
            );
            throw err;
        }
    }

    _recomputeMinMax() {
        const vals = Object.values(this.state.cells).filter((v) => v != null);
        this.state.minPrice = vals.length ? Math.min(...vals) : 0;
        this.state.maxPrice = vals.length ? Math.max(...vals) : 0;
    }

    // ──────────────────────────────────────────────────────────────────────
    // Bulk actions
    // ──────────────────────────────────────────────────────────────────────

    async onRowBulk(spaceTypeId) {
        const raw = window.prompt(_t("Apply price to all dates in this row:"));
        if (raw === null) return;
        const price = parseFloat(raw);
        if (isNaN(price) || price < 0) return;
        this.state.loading = true;
        try {
            for (const ds of this.state.dates) {
                await this._writeCell(spaceTypeId, ds, price);
            }
        } finally {
            this.state.loading = false;
        }
    }

    async onColumnBulk(dateStr) {
        const raw = window.prompt(
            _t("Apply price to all space types on this date:"),
        );
        if (raw === null) return;
        const price = parseFloat(raw);
        if (isNaN(price) || price < 0) return;
        this.state.loading = true;
        try {
            for (const st of this.state.spaceTypes) {
                await this._writeCell(st.id, dateStr, price);
            }
        } finally {
            this.state.loading = false;
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    // Copy range dialog
    // ──────────────────────────────────────────────────────────────────────

    onOpenCopyDialog() {
        this.state.copyDialog.open = true;
        this.state.copyDialog.srcFrom = this.state.dates[0] || "";
        this.state.copyDialog.srcTo =
            this.state.dates[Math.min(6, this.state.dates.length - 1)] || "";
        this.state.copyDialog.dstFrom = this.state.dates[7] || "";
        this.state.copyDialog.dstTo =
            this.state.dates[Math.min(13, this.state.dates.length - 1)] || "";
    }

    onCloseCopyDialog() {
        this.state.copyDialog.open = false;
    }

    async onConfirmCopy() {
        const c = this.state.copyDialog;
        if (!c.srcFrom || !c.srcTo || !c.dstFrom || !c.dstTo) return;
        this.state.loading = true;
        try {
            await this.orm.call(
                "hospitality.rate.plan",
                "action_copy_range",
                [this.state.rateCodeId, c.srcFrom, c.srcTo,
                 c.dstFrom, c.dstTo],
            );
            this.state.copyDialog.open = false;
            await this._loadPlans();
            this.notification.add(_t("Prices copied"), { type: "success" });
        } catch (err) {
            console.error("Rate Calendar: copy failed", err);
            this.notification.add(_t("Copy failed"), { type: "danger" });
            throw err;
        } finally {
            this.state.loading = false;
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    // Template helpers
    // ──────────────────────────────────────────────────────────────────────

    get windowOptions() {
        return DATE_WINDOW_OPTIONS;
    }

    cellKey(spaceTypeId, dateStr) {
        return `${spaceTypeId}:${dateStr}`;
    }

    cellPrice(spaceTypeId, dateStr) {
        const v = this.state.cells[this.cellKey(spaceTypeId, dateStr)];
        return v != null ? v.toFixed(2) : "";
    }

    isEditing(spaceTypeId, dateStr) {
        return this.state.editingKey === this.cellKey(spaceTypeId, dateStr);
    }

    isSaving(spaceTypeId, dateStr) {
        return this.state.savingKey === this.cellKey(spaceTypeId, dateStr);
    }

    isJustSaved(spaceTypeId, dateStr) {
        return this.state.justSavedKey === this.cellKey(spaceTypeId, dateStr);
    }

    cellStyle(spaceTypeId, dateStr) {
        const v = this.state.cells[this.cellKey(spaceTypeId, dateStr)];
        if (v == null) return "";
        const { minPrice, maxPrice } = this.state;
        if (maxPrice <= minPrice) {
            return "background-color: #eef5ff;";
        }
        const ratio = (v - minPrice) / (maxPrice - minPrice);
        const hue = (1 - ratio) * 120;
        return `background-color: hsl(${hue}, 70%, 88%);`;
    }

    dateLabel(dateStr) {
        const d = new Date(dateStr);
        const wd = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][d.getDay()];
        const dd = String(d.getDate()).padStart(2, "0");
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        return `${wd}\n${dd}/${mm}`;
    }

    isWeekend(dateStr) {
        const d = new Date(dateStr);
        const day = d.getDay();
        return day === 0 || day === 6;
    }
}

registry
    .category("actions")
    .add("hospitality_rate.rate_calendar", RateCalendarRenderer);