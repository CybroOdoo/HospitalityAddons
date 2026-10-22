/** @odoo-module **/

import { registry } from "@web/core/registry";

function setDateInput(selector, isoDate) {
    const el = document.querySelector(selector);
    el.value = isoDate;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

registry.category("web_tour.tours").add("hospitality_be04_booking_flow_tour", {
    url: "/booking",
    steps: () => [
        {
            content: "Search page loaded",
            trigger: "#be_search_form",
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
            content: "Submit search",
            trigger: "#be_search_submit",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Results page loaded",
            trigger: ".o_be_results",
        },
        {
            content: "Go to cart",
            trigger: "body",
            run: () => { window.location.href = "/booking/cart"; },
            expectUnloadPage: true,
        },
        {
            content: "Cart page loaded",
            trigger: ".o_be_cart",
        },
        {
            content: "Go to checkout",
            trigger: "body",
            run: () => { window.location.href = "/booking/checkout"; },
            expectUnloadPage: true,
        },
        {
            content: "Checkout page loaded",
            trigger: ".o_be_checkout",
        },
        {
            content: "Go to lookup page",
            trigger: "body",
            run: () => { window.location.href = "/booking/lookup"; },
            expectUnloadPage: true,
        },
        {
            content: "Lookup page loaded",
            trigger: ".o_be_lookup",
        },
    ],
});