/** @odoo-module **/

import { registry } from "@web/core/registry";
registry.category("web_tour.tours").add("test_restrictions_matrix_renders", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Hospitality app",
            trigger: '.o_app[data-menu-xmlid="hospitality_base.menu_hospitality_root"]',
            run: "click",
        },
        {
            content: "Open Restrictions Matrix Action",
            // Adjust this trigger to match your actual menu item for Restrictions
            trigger: 'a[data-menu-xmlid="hospitality_rate.menu_hospitality_restrictions"]',
            run: "click",
        },
        {
            content: "Check if matrix rendered by looking for All Types row",
            trigger: 'th.o_rm_row_header:contains("All Types")',
            isCheck: true,
        },
        {
            content: "Check if the toolbar rendered",
            trigger: '.o_rm_rate_code_select',
            isCheck: true,
        }
    ],
});

registry.category("web_tour.tours").add("test_restrictions_matrix_set_closed", {
    test: true,
    url: "/web",
    steps: () => [
        // Assume the python test opens the action directly before this tour starts
        {
            content: "Wait for grid to load",
            trigger: '.o_rm_cell',
            isCheck: true,
        },
        {
            content: "Simulate Drag Selection (MouseDown -> MouseEnter -> MouseUp)",
            trigger: '.o_restrictions_matrix tbody tr:nth-child(2) td.o_rm_cell:first',
            run: () => {
                // Select row 2 (first actual space type), cells 1 to 3
                const cells = document.querySelectorAll('.o_restrictions_matrix tbody tr:nth-child(2) td.o_rm_cell');
                const matrix = document.querySelector('.o_restrictions_matrix');

                if (cells.length >= 3) {
                    cells[0].dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                    cells[2].dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                    matrix.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                }
            },
        },
        {
            content: "Wait for Wizard to Open",
            trigger: '.o_rm_wizard_modal',
            isCheck: true,
        },
        {
            content: "Click 'Set Closed' button",
            trigger: 'button.o_rm_wiz_set_closed',
            run: "click",
        },
        {
            content: "Verify cells turned red (o_rm_closed class applied)",
            trigger: '.o_restrictions_matrix tbody tr:nth-child(2) td.o_rm_cell:first.o_rm_closed',
            isCheck: true,
        }
    ],
});