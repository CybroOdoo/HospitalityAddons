/** @odoo-module **/
// ---------------------------------------------------------------------------
//  Monogram and tint for an app that carries no web_icon.
//
//  Tints mirror $ht-app-tints in scss/variables.scss; keep the two in
//  step when a family is added.
// ---------------------------------------------------------------------------

export const TINTS = [
    "brass", "blue", "cream", "mint", "teal", "lilac", "peach", "neutral",
];

// Explicit assignments, keyed on root-menu xmlid.
const BY_XMLID = {
    "hospitality_base.menu_hm_front_office": "brass",
    "hospitality_base.menu_hm_rooms": "blue",
    "hospitality_base.menu_hm_finance": "mint",
    "hospitality_booking_engine.menu_booking_engine_root": "teal",
    "hospitality_base.menu_hospitality_reports": "lilac",
    "hospitality_base.menu_hospitality_root": "neutral",
};

// Fallback by name, so a future app lands on a sensible colour even
// before anyone maps its xmlid.
const BY_NAME = [
    [/front\s*office|reception|room\s*rack|reservation/i, "brass"],
    [/room|housekeep|maintenance/i, "blue"],
    [/restaurant|banquet|food|beverage|kitchen|f&b/i, "cream"],
    [/folio|revenue|finance|cashier|rate|account/i, "mint"],
    [/distribution|channel|booking\s*engine/i, "teal"],
    [/report|analytic|dashboard/i, "lilac"],
    [/inventory|stock|purchase/i, "peach"],
];

/**
 * True when the app carries artwork of its own.
 *
 * Odoo never leaves webIconData empty: menu_helpers.js substitutes
 * /web/static/img/default_icon_app.png for any menu without a web_icon.
 * Treating that as a real icon means every new root renders as the same
 * grey box, so it is explicitly excluded and the monogram takes over.
 */
export function hasRealIcon(app) {
    const data = app.webIconData;
    return !!data && !String(data).includes("default_icon_app");
}

/** "Front Office" -> "FO"; "Rooms" -> "R". */
export function monogramFor(name) {
    const words = (name || "")
        .replace(/[^\p{L}\p{N}\s&]/gu, " ")
        .split(/\s+/)
        .filter((w) => w && w.toLowerCase() !== "and" && w !== "&");
    if (!words.length) {
        return "?";
    }
    if (words.length === 1) {
        return words[0][0].toUpperCase();
    }
    return (words[0][0] + words[1][0]).toUpperCase();
}

/** Stable tint: by xmlid, then by name, then by hash of the name. */
export function tintFor(app) {
    if (app.xmlid && BY_XMLID[app.xmlid]) {
        return BY_XMLID[app.xmlid];
    }
    for (const [re, tint] of BY_NAME) {
        if (re.test(app.name || "")) {
            return tint;
        }
    }
    let hash = 0;
    for (const ch of app.name || "") {
        hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
    }
    return TINTS[hash % TINTS.length];
}
