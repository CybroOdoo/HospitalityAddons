/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// ─── helpers ──────────────────────────────────────────────────────────────────

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

function cellColorClass(flags) {
    if (!flags) return "o_rm_open";
    if (flags.closed) return "o_rm_closed";
    if (flags.cta) return "o_rm_cta";
    if (flags.ctd) return "o_rm_ctd";
    if (flags.min_stay > 0 || flags.max_stay > 0) return "o_rm_stay";
    return "o_rm_open";
}

function cellTitle(flags) {
    if (!flags) return _t("Open");
    const parts = [];
    if (flags.closed) parts.push(_t("Closed"));
    if (flags.cta) parts.push(_t("CTA"));
    if (flags.ctd) parts.push(_t("CTD"));
    if (flags.min_stay > 0) parts.push(_t("Min %s", flags.min_stay));
    if (flags.max_stay > 0) parts.push(_t("Max %s", flags.max_stay));
    return parts.length ? parts.join(", ") : _t("Open");
}

// ─── Component ────────────────────────────────────────────────────────────────

export class RestrictionsMatrix extends Component {
    static template = "hospitality_rate.RestrictionsMatrix";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        this.state = useState({
            rateCodes: [],
            rateCodeId: false,
            propertyId: false,
            startDate: fmtDate(today),
            windowDays: 14,
            spaceTypes: [],
            dates: [],
            cells: {},
            loading: true,
            panel: {
                open: false,
                spaceTypeId: false,
                spaceTypeName: "",
                dateStr: "",
                recordId: false,
                closed: false,
                cta: false,
                ctd: false,
                min_stay: 0,
                max_stay: 0,
                no_show_charge_pct: 100,
                saving: false,
            },
            drag: {
                active: false,
                startSpaceIdx: -1,
                startDateIdx: -1,
                endSpaceIdx: -1,
                endDateIdx: -1,
            },
            wizard: {
                open: false,
                closed: false,
                cta: false,
                ctd: false,
                min_stay: 0,
                max_stay: 0,
                no_show_charge_pct: 100,
                saving: false,
            },
        });

        onWillStart(async () => {
            await this._loadRateCodes();
            if (this.state.rateCodeId) {
                await this._loadGrid();
            } else {
                this.state.loading = false;
            }
        });
    }

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
            this.state.propertyId = codes[0].property_id ? codes[0].property_id[0] : false;
        }
    }

    async _loadSpaceTypes() {
        const domain = this.state.propertyId ? [["property_id", "=", this.state.propertyId]] : [];
        const rows = await this.orm.searchRead(
            "hospitality.space.type",
            domain,
            ["id", "name"],
            { limit: 100 },
        );
        this.state.spaceTypes = [{ id: 0, name: _t("All Types") }, ...rows];
    }

    _computeDates() {
        const start = new Date(this.state.startDate);
        const dates = [];
        for (let i = 0; i < this.state.windowDays; i++) {
            dates.push(fmtDate(addDays(start, i)));
        }
        this.state.dates = dates;
    }

    async _loadRestrictions() {
        if (!this.state.rateCodeId || !this.state.dates.length) {
            this.state.cells = {};
            return;
        }
        const first = this.state.dates[0];
        const last = this.state.dates[this.state.dates.length - 1];

        const records = await this.orm.searchRead(
            "hospitality.rate.restriction",
            [
                ["rate_code_id", "=", this.state.rateCodeId],
                ["date_from", "<=", last],
                ["date_to", ">=", first],
            ],
            [
                "id", "space_type_id", "date_from", "date_to",
                "closed", "cta", "ctd", "min_stay", "max_stay", "no_show_charge_pct",
            ],
            { limit: 10000 },
        );

        const cells = {};
        for (const rec of records) {
            const stRaw = rec.space_type_id;
            const stId = stRaw ? stRaw[0] : 0;
            const dFrom = new Date(rec.date_from);
            const dTo = new Date(rec.date_to);

            for (const ds of this.state.dates) {
                const d = new Date(ds);
                if (d >= dFrom && d <= dTo) {
                    const key = `${stId}:${ds}`;
                    const prev = cells[key] || {};
                    cells[key] = {
                        id: rec.id,
                        closed: rec.closed || prev.closed || false,
                        cta: rec.cta || prev.cta || false,
                        ctd: rec.ctd || prev.ctd || false,
                        min_stay: Math.max(rec.min_stay || 0, prev.min_stay || 0),
                        max_stay: Math.max(rec.max_stay || 0, prev.max_stay || 0),
                        no_show_charge_pct: rec.no_show_charge_pct ?? 100,
                    };
                }
            }
        }
        this.state.cells = cells;
    }

    async _loadGrid() {
        this.state.loading = true;
        try {
            this._computeDates();
            await this._loadSpaceTypes();
            await this._loadRestrictions();
        } finally {
            this.state.loading = false;
        }
    }

    async onRateCodeChange(ev) {
        const id = parseInt(ev.target.value, 10);
        this.state.rateCodeId = id;
        const rc = this.state.rateCodes.find((r) => r.id === id);
        this.state.propertyId = rc && rc.property_id ? rc.property_id[0] : false;
        await this._loadGrid();
    }

    async onStartDateChange(ev) {
        this.state.startDate = ev.target.value;
        await this._loadGrid();
    }

    async onWindowChange(ev) {
        this.state.windowDays = parseInt(ev.target.value, 10);
        await this._loadGrid();
    }

    onCellClick(spaceTypeId, spaceTypeName, dateStr) {
        if (this._dragJustEnded) {
            this._dragJustEnded = false;
            return;
        }
        const flags = this.state.cells[`${spaceTypeId}:${dateStr}`];
        const p = this.state.panel;
        p.open = true;
        p.spaceTypeId = spaceTypeId;
        p.spaceTypeName = spaceTypeName;
        p.dateStr = dateStr;
        p.recordId = flags ? flags.id : false;
        p.closed = flags ? flags.closed : false;
        p.cta = flags ? flags.cta : false;
        p.ctd = flags ? flags.ctd : false;
        p.min_stay = flags ? flags.min_stay : 0;
        p.max_stay = flags ? flags.max_stay : 0;
        p.no_show_charge_pct = flags ? flags.no_show_charge_pct : 100;
        p.saving = false;
    }

    onClosePanel() {
        this.state.panel.open = false;
    }

    async onSavePanel() {
        const p = this.state.panel;

        // VALIDATION: Check if Min Stay is logically greater than Max Stay
        if (p.min_stay > 0 && p.max_stay > 0 && p.min_stay > p.max_stay) {
            this.notification.add(_t("Minimum stay cannot be greater than Maximum stay."), { type: "danger" });
            return; // Stop saving
        }

        p.saving = true;
        try {
            await this.orm.call(
                "hospitality.rate.restriction",
                "action_upsert", // The backend developer MUST update the python file for this to work
                [
                    this.state.rateCodeId,
                    p.spaceTypeId || false,
                    p.dateStr,
                    p.dateStr,
                ],
                {
                    closed: p.closed,
                    cta: p.cta,
                    ctd: p.ctd,
                    min_stay: p.min_stay,
                    max_stay: p.max_stay,
                    no_show_charge_pct: p.no_show_charge_pct,
                },
            );
            await this._loadRestrictions();
            p.open = false;
            this.notification.add(_t("Restriction saved"), { type: "success" });
        } catch (err) {
            this.notification.add(_t("Save failed"), { type: "danger" });
            throw err;
        } finally {
            p.saving = false;
        }
    }

    onCellMouseDown(spaceIdx, dateIdx) {
        this.state.drag.active = true;
        this.state.drag.startSpaceIdx = spaceIdx;
        this.state.drag.startDateIdx = dateIdx;
        this.state.drag.endSpaceIdx = spaceIdx;
        this.state.drag.endDateIdx = dateIdx;
    }

    onCellMouseEnter(spaceIdx, dateIdx) {
        if (!this.state.drag.active) return;
        this.state.drag.endSpaceIdx = spaceIdx;
        this.state.drag.endDateIdx = dateIdx;
    }

    onGridMouseUp() {
        if (!this.state.drag.active) return;
        this.state.drag.active = false;
        const { startSpaceIdx, startDateIdx, endSpaceIdx, endDateIdx } = this.state.drag;
        const minS = Math.min(startSpaceIdx, endSpaceIdx);
        const maxS = Math.max(startSpaceIdx, endSpaceIdx);
        const minD = Math.min(startDateIdx, endDateIdx);
        const maxD = Math.max(startDateIdx, endDateIdx);
        if (maxS > minS || maxD > minD) {
            this._dragJustEnded = true;
            this._openWizard(minS, maxS, minD, maxD);
        }
    }

    _openWizard(minS, maxS, minD, maxD) {
        this._selection = { minS, maxS, minD, maxD };
        const w = this.state.wizard;
        w.open = true;
        w.closed = false;
        w.cta = false;
        w.ctd = false;
        w.min_stay = 0;
        w.max_stay = 0;
        w.no_show_charge_pct = 100;
        w.saving = false;
    }

    onCloseWizard() {
        this.state.wizard.open = false;
    }

    async onSetClosedWizard() {
        this.state.wizard.closed = true;
        await this.onApplyWizard();
    }

    async onApplyWizard() {
        const w = this.state.wizard;

        // VALIDATION: Check if Min Stay is logically greater than Max Stay
        if (w.min_stay > 0 && w.max_stay > 0 && w.min_stay > w.max_stay) {
            this.notification.add(_t("Minimum stay cannot be greater than Maximum stay."), { type: "danger" });
            return; // Stop saving
        }

        w.saving = true;
        const { minS, maxS, minD, maxD } = this._selection;
        try {
            for (let si = minS; si <= maxS; si++) {
                const st = this.state.spaceTypes[si];
                const stId = st.id === 0 ? false : st.id;
                const dateFrom = this.state.dates[minD];
                const dateTo = this.state.dates[maxD];
                await this.orm.call(
                    "hospitality.rate.restriction",
                    "action_upsert", // The backend developer MUST update the python file for this to work
                    [this.state.rateCodeId, stId, dateFrom, dateTo],
                    {
                        closed: w.closed,
                        cta: w.cta,
                        ctd: w.ctd,
                        min_stay: w.min_stay,
                        max_stay: w.max_stay,
                        no_show_charge_pct: w.no_show_charge_pct,
                    },
                );
            }
            await this._loadRestrictions();
            w.open = false;
            this.notification.add(
                _t("Restriction applied to %s space type(s), %s date(s)",
                    maxS - minS + 1, maxD - minD + 1),
                { type: "success" },
            );
        } catch (err) {
            this.notification.add(_t("Apply failed"), { type: "danger" });
            throw err;
        } finally {
            w.saving = false;
        }
    }

    cellValue(spaceTypeId, dateStr) {
        const flags = this.state.cells[`${spaceTypeId}:${dateStr}`];

        if (!flags) {
            return "";
        }

        const parts = [];

        if (flags.closed) {
            parts.push("Closed");
        }

        if (flags.cta) {
            parts.push("CTA");
        }

        if (flags.ctd) {
            parts.push("CTD");
        }

        if (flags.min_stay > 0) {
            parts.push(`MLOS ${flags.min_stay}`);
        }

        if (flags.max_stay > 0) {
            parts.push(`Max ${flags.max_stay}`);
        }

        return parts.join(" / ");
    }

    cellColorClass(spaceTypeId, dateStr) {
        return cellColorClass(this.state.cells[`${spaceTypeId}:${dateStr}`]);
    }

    cellTitle(spaceTypeId, dateStr) {
        return cellTitle(this.state.cells[`${spaceTypeId}:${dateStr}`]);
    }

    isSelected(spaceIdx, dateIdx) {
        // 1. Actively dragging multiple cells
        if (this.state.drag.active) {
            const minS = Math.min(this.state.drag.startSpaceIdx, this.state.drag.endSpaceIdx);
            const maxS = Math.max(this.state.drag.startSpaceIdx, this.state.drag.endSpaceIdx);
            const minD = Math.min(this.state.drag.startDateIdx, this.state.drag.endDateIdx);
            const maxD = Math.max(this.state.drag.startDateIdx, this.state.drag.endDateIdx);
            return (spaceIdx >= minS && spaceIdx <= maxS && dateIdx >= minD && dateIdx <= maxD);
        }

        // 2. Wizard is currently open (Multi-cell selection)
        if (this.state.wizard.open && this._selection) {
            const { minS, maxS, minD, maxD } = this._selection;
            return (spaceIdx >= minS && spaceIdx <= maxS && dateIdx >= minD && dateIdx <= maxD);
        }

        // 3. Side Panel is currently open (Single-cell selection)
        if (this.state.panel.open) {
            const st = this.state.spaceTypes[spaceIdx];
            const ds = this.state.dates[dateIdx];
            // Keep the blue box on the exact cell matching the side panel
            return (st.id === this.state.panel.spaceTypeId && ds === this.state.panel.dateStr);
        }

        return false;
    }

    isWeekend(dateStr) {
        const day = new Date(dateStr).getDay();
        return day === 0 || day === 6;
    }

    dateLabel(dateStr) {
        const d = new Date(dateStr);
        const wd = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][d.getDay()];
        const dd = String(d.getDate()).padStart(2, "0");
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        return `${wd}\n${dd}/${mm}`;
    }
}

registry
    .category("actions")
    .add("hospitality_rate.restrictions_matrix", RestrictionsMatrix);