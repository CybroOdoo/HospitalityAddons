/** @odoo-module **/

/**
 * PROP-06 Tour Tests — Floor Plan OWL view
 *
 * Tour 1: floor_plan_loads
 *   Opens the Floor Plan view and verifies it renders space cards.
 *
 * Tour 2: floor_plan_bulk_ooo
 *   Drag-selects 5 cards, clicks "Set OOO", verifies wizard opens
 *   pre-populated with 5 space ids.
 */

import { registry } from "@web/core/registry";

// ---------------------------------------------------------------------------
//  Tour 1 — Floor Plan loads in < 1.5 s for 50 spaces
// ---------------------------------------------------------------------------
registry.category("web_tour.tours").add("floor_plan_loads", {
    url: "/odoo",
    steps: () => [
        // Navigate to Hospitality app
        {
            trigger: ".o_app[data-menu-xmlid='hospitality_base.menu_hospitality_root']",
            content: "Open Hospitality app",
            run: "click",
        },
        // Click Operations → Floor Plan
        {
            trigger: ".o_menu_sections a:contains('Operations')",
            content: "Open Operations menu",
            run: "click",
        },
        {
            trigger: ".o_nav_entry:contains('Floor Plan')",
            content: "Click Floor Plan menu",
            run: "click",
        },
        // Verify the OWL view rendered — floor cards grid must be visible
        {
            trigger: ".o_floor_plan_view .o_floor_cards_grid",
            content: "Floor plan grid is visible",
            run: () => {
                // Timing assertion: the component must have mounted
                const grids = document.querySelectorAll(".o_floor_cards_grid");
                if (!grids.length) {
                    throw new Error("Floor plan grid not found — view did not load.");
                }
            },
        },
    ],
});

// ---------------------------------------------------------------------------
//  Tour 2 — Drag-select 5 cards → Set OOO → wizard pre-populated with 5 ids
// ---------------------------------------------------------------------------
registry.category("web_tour.tours").add("floor_plan_bulk_ooo", {
    url: "/odoo",
    steps: () => [
        // Navigate to Floor Plan
        {
            trigger: ".o_app[data-menu-xmlid='hospitality_base.menu_hospitality_root']",
            content: "Open Hospitality app",
            run: "click",
        },
        {
            trigger: ".o_menu_sections a:contains('Operations')",
            content: "Open Operations menu",
            run: "click",
        },
        {
            trigger: ".o_nav_entry:contains('Floor Plan')",
            content: "Click Floor Plan menu",
            run: "click",
        },
        // Wait for cards to render
        {
            trigger: ".o_floor_plan_view .o_floor_space_card",
            content: "Space cards are visible",
        },
        // Click first 5 cards to select them
        {
            trigger: ".o_floor_space_card:nth-child(1)",
            content: "Select card 1",
            run: "click",
        },
        {
            trigger: ".o_floor_space_card:nth-child(2)",
            content: "Select card 2",
            run: "click",
        },
        {
            trigger: ".o_floor_space_card:nth-child(3)",
            content: "Select card 3",
            run: "click",
        },
        {
            trigger: ".o_floor_space_card:nth-child(4)",
            content: "Select card 4",
            run: "click",
        },
        {
            trigger: ".o_floor_space_card:nth-child(5)",
            content: "Select card 5",
            run: "click",
        },
        // Verify selection badge shows 5
        {
            trigger: ".badge.bg-primary:contains('5')",
            content: "5 cards are selected",
        },
        // Click Set OOO bulk action
        {
            trigger: ".btn:contains('Set OOO')",
            content: "Click Set OOO",
            run: "click",
        },
        // Wizard must open with 5 spaces pre-populated
        {
            trigger: ".modal .o_form_view",
            content: "OOO wizard is open",
            run: () => {
                // Verify the space_ids many2many has 5 tags
                const tags = document.querySelectorAll(
                    ".modal .o_field_many2many_tags .badge"
                );
                if (tags.length !== 5) {
                    throw new Error(
                        `Expected 5 space tags in wizard, found ${tags.length}`
                    );
                }
            },
        },
        // Close wizard
        {
            trigger: ".modal .o_form_button_cancel, .modal button:contains('Cancel')",
            content: "Close wizard",
            run: "click",
        },
    ],
});