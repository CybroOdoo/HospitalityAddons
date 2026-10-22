/** @odoo-module **/

import { registry } from "@web/core/registry";

// BE-06: full integration tour — the real end-to-end flow (search ->
// results -> select -> cart -> checkout -> pay -> confirmation)
// against demo data, as opposed to BE-04's tour which only proved
// navigation/rendering with stub data.
function setDateInput(selector, isoDate) {
    const el = document.querySelector(selector);
    el.value = isoDate;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

registry.category("web_tour.tours").add("hospitality_be06_full_booking_flow_tour", {
    url: "/booking",
    steps: () => [
        {
            content: "Search page loaded",
            trigger: "#be_search_form",
        },
        {
            // Matched by name rather than a hardcoded option value/ID,
            // since NYC01's actual database id isn't knowable here.
            //
            // Selecting a property fires the select's onchange handler,
            // which navigates via window.location.href — this is a real
            // page unload, so it must be declared with
            // expectUnloadPage: true or the tour runner fails the step
            // instead of waiting for the new page to load.
            content: "Select the NYC01 property",
            trigger: "#be_property_id",
            run: () => {
                const select = document.querySelector("#be_property_id");
                const option = Array.from(select.options).find(
                    (o) => o.textContent.includes("NYC")
                );
                if (option) {
                    select.value = option.value;
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                }
            },
            expectUnloadPage: true,
        },
        {
            content: "Set arrival date",
            trigger: "#be_arrival",
            run: () => setDateInput("#be_arrival", "2026-09-01"),
        },
        {
            content: "Set departure date",
            trigger: "#be_departure",
            run: () => setDateInput("#be_departure", "2026-09-04"),
        },
        {
            content: "Enter the SUMMER10 promo code",
            trigger: "#be_promo_code",
            run: "edit SUMMER10",
        },
        {
            content: "Submit search",
            trigger: "#be_search_submit",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Results page loaded with at least one room",
            trigger: ".o_be_result_card",
        },
        {
            content: "Click Book on the first result",
            trigger: ".o_be_book_btn",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Room detail page loaded",
            trigger: "#be_add_to_cart",
        },
        {
            content: "Add to cart",
            trigger: "#be_add_to_cart",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Cart page loaded with a line",
            trigger: ".o_be_cart_table",
        },
        {
            content: "Go to checkout",
            trigger: "#be_checkout_btn",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Checkout page loaded",
            trigger: "#be_checkout_form",
        },
        {
            content: "Fill guest name",
            trigger: "#be_guest_name",
            run: "edit BE-06 Tour Guest",
        },
        {
            content: "Fill guest email",
            trigger: "#be_guest_email",
            run: "edit be06-tour@example.com",
        },
        {
            content: "Fill guest phone",
            trigger: "#be_guest_phone",
            run: "edit +1 555 010 0006",
        },
        {
            // The radio itself is visually hidden now: each provider is a
            // clickable tile, and the <label> is what a guest actually hits.
            // A tour click on the hidden input is not a real interaction.
            content: "Select the first available payment method",
            trigger: ".o_be_payment_providers .form-check-label",
            run: "click",
        },
        {
            content: "Confirm and pay",
            trigger: "#be_checkout_submit",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Confirmation page loaded with a reservation reference",
            trigger: "#be_reservation_ref",
        },
    ],
});