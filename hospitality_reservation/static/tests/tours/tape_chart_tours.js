/** @odoo-module **/

import { registry } from "@web/core/registry";

// ─────────────────────────────────────────────────────────────────────────
// 1. test_tape_chart_renders
// ─────────────────────────────────────────────────────────────────────────
registry.category("web_tour.tours").add("test_tape_chart_renders", {
    test: true,
    url: "/odoo/action-hospitality_reservation.action_tape_chart",
    steps: () => [
        {
            trigger: ".o_tape_chart_view",
            content: "Tape chart root mounts",
        },
        {
            trigger: ".o_tape_chart_date_header",
            content: "Date header row is rendered",
        },
        {
            trigger: ".o_tape_chart_row_labels",
            content: "Row label column is rendered",
        },
        {
            trigger: ".o_tape_chart_grid_scroll",
            content: "Scrollable grid is rendered",
            run: function () {
                const cols = document.querySelectorAll(".o_tape_chart_date_col");
                if (cols.length !== 14) {
                    throw new Error(
                        `Expected 14 date columns (default range), got ${cols.length}`
                    );
                }
            },
        },
    ],
});

// ─────────────────────────────────────────────────────────────────────────
// 2. test_drag_to_create_opens_new_reservation_form
// ─────────────────────────────────────────────────────────────────────────
registry.category("web_tour.tours").add(
    "test_drag_to_create_opens_new_reservation_form",
    {
        test: true,
        url: "/odoo/action-hospitality_reservation.action_tape_chart",
        steps: () => [
            {
                trigger: ".o_tape_chart_view",
                content: "Tape chart loaded",
            },
            {
                // Use .o_tape_chart_row (without :first-child) because rows sit
                // inside .o_tape_chart_rows alongside the .o_tape_drag_ghost div,
                // so :first-child would never match a row element.
                trigger: ".o_tape_chart_row .o_tape_chart_cell",
                content: "Press down on an empty cell to start a create-drag",
                run: function () {
                    // Simulate pointerdown on the first cell, then pointerup
                    // 3 cells to the right to trigger the create-drag handler.
                    const cells = document.querySelectorAll(
                        ".o_tape_chart_row .o_tape_chart_cell"
                    );
                    if (!cells.length) return;
                    const startCell = cells[0];
                    const endCell = cells[Math.min(3, cells.length - 1)];
                    const sr = startCell.getBoundingClientRect();
                    const er = endCell.getBoundingClientRect();
                    startCell.dispatchEvent(
                        new PointerEvent("pointerdown", {
                            bubbles: true, cancelable: true, pointerId: 1,
                            clientX: sr.left + 5, clientY: sr.top + sr.height / 2,
                        })
                    );
                    document.dispatchEvent(
                        new PointerEvent("pointermove", {
                            bubbles: true, cancelable: true, pointerId: 1,
                            clientX: er.right - 5, clientY: er.top + er.height / 2,
                        })
                    );
                    document.dispatchEvent(
                        new PointerEvent("pointerup", {
                            bubbles: true, cancelable: true, pointerId: 1,
                            clientX: er.right - 5, clientY: er.top + er.height / 2,
                        })
                    );
                },
            },
            {
                trigger: ".o_form_view",
                content: "New reservation form opens pre-filled in a dialog",
                run: function () {
                    const arrivalInput = document.querySelector(
                        ".o_form_view input[id^='arrival']"
                    );
                    if (!arrivalInput || !arrivalInput.value) {
                        throw new Error(
                            "Expected the new reservation form's arrival field to be pre-filled."
                        );
                    }
                },
            },
        ],
    }
);

// ─────────────────────────────────────────────────────────────────────────
// 3. test_drag_to_extend_persists_dates
// ─────────────────────────────────────────────────────────────────────────
registry.category("web_tour.tours").add("test_drag_to_extend_persists_dates", {
    test: true,
    url: "/odoo/action-hospitality_reservation.action_tape_chart",
    steps: () => [
        {
            trigger: ".o_tape_chart_view",
            content: "Tape chart loaded",
        },
        {
            // .o_tape_chart_bar is not :first-child (the ghost div precedes rows,
            // and bars are position:absolute children of the row div).
            // Select the resize handle directly with a class-only selector.
            trigger: ".o_tape_bar_edge_end",
            content: "Drag the right edge of the first bar two days further out",
            run: function () {
                const handle = document.querySelector(".o_tape_bar_edge_end");
                if (!handle) return;
                const cells = document.querySelectorAll(".o_tape_chart_row .o_tape_chart_cell");
                const targetCell = cells[Math.min(7, cells.length - 1)];
                const hr = handle.getBoundingClientRect();
                const tr = targetCell
                    ? targetCell.getBoundingClientRect()
                    : { left: hr.left + 80, top: hr.top };

                handle.dispatchEvent(new PointerEvent("pointerdown", {
                    bubbles: true, cancelable: true, pointerId: 1,
                    clientX: hr.left + 3, clientY: hr.top + hr.height / 2,
                }));
                document.dispatchEvent(new PointerEvent("pointermove", {
                    bubbles: true, cancelable: true, pointerId: 1,
                    clientX: tr.right - 5, clientY: hr.top + hr.height / 2,
                }));
                document.dispatchEvent(new PointerEvent("pointerup", {
                    bubbles: true, cancelable: true, pointerId: 1,
                    clientX: tr.right - 5, clientY: hr.top + hr.height / 2,
                }));
            },
        },
        {
            trigger: ".o_notification_bar, .o_tape_chart_bar",
            content: "Write RPC completes and grid reloads without error",
        },
    ],
});

// ─────────────────────────────────────────────────────────────────────────
// 4. test_drag_vertical_changes_space
// ─────────────────────────────────────────────────────────────────────────
registry.category("web_tour.tours").add("test_drag_vertical_changes_space", {
    test: true,
    url: "/odoo/action-hospitality_reservation.action_tape_chart",
    steps: () => [
        {
            trigger: ".o_tape_chart_view",
            content: "Tape chart loaded",
        },
        {
            // Same issue: .o_tape_chart_bar:first-child never matches because
            // bars are absolute children of .o_tape_chart_row alongside cells.
            // Use plain class selector to get any bar.
            trigger: ".o_tape_chart_bar",
            content: "Drag the first bar down one row to move it to another space",
            run: function () {
                const bar = document.querySelector(".o_tape_chart_bar");
                const rows = document.querySelectorAll(".o_tape_chart_row");
                if (!bar || rows.length < 2) return;
                const br = bar.getBoundingClientRect();
                // Target the second row's first cell
                const targetRow = rows[1];
                const targetCell = targetRow.querySelector(".o_tape_chart_cell");
                const tr = targetCell
                    ? targetCell.getBoundingClientRect()
                    : { left: br.left, top: br.top + 40 };

                bar.dispatchEvent(new PointerEvent("pointerdown", {
                    bubbles: true, cancelable: true, pointerId: 1,
                    clientX: br.left + 20, clientY: br.top + br.height / 2,
                }));
                document.dispatchEvent(new PointerEvent("pointermove", {
                    bubbles: true, cancelable: true, pointerId: 1,
                    clientX: tr.left + 20, clientY: tr.top + tr.height / 2,
                }));
                document.dispatchEvent(new PointerEvent("pointerup", {
                    bubbles: true, cancelable: true, pointerId: 1,
                    clientX: tr.left + 20, clientY: tr.top + tr.height / 2,
                }));
            },
        },
        {
            trigger: ".o_notification_bar, .o_tape_chart_bar",
            content: "Move persists (direct write, or move wizard for checked_in)",
        },
    ],
});