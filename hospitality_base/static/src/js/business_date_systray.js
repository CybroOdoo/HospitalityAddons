/** @odoo-module **/
// ---------------------------------------------------------------------------
//  Business-date pill in the navbar systray.
//
//  The date belongs in the chrome, not in the drawer body: it is true on
//  every screen, not only on the landing page.
// ---------------------------------------------------------------------------

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class BusinessDateSystray extends Component {
    static template = "hospitality_base.BusinessDateSystray";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ date: "" });

        onWillStart(async () => {
            try {
                const data = await this.orm.call(
                    "hospitality.theme.home", "get_business_date", [], {}
                );
                this.state.date = data.business_date || "";
            } catch {
                // No property, or the suite is not installed: show
                // nothing rather than an empty pill.
                this.state.date = "";
            }
        });
    }
}

// Not mounted in the systray: the drawer's left column now carries the
// date prominently, and the pill beside it read as a duplicate. The
// component is kept whole and exported, so putting it back is a one-line
// registration (sequence 5 puts it left of the activity and user menus):
//
//   registry.category("systray").add(
//       "hospitality_base.business_date",
//       { Component: BusinessDateSystray },
//       { sequence: 5 },
//   );

