/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class WeekdayMaskField extends Component {
    static template = "hospitality_rate.WeekdayMaskField";
    static props = { ...standardFieldProps };

    static DAYS = [
        { bit: 0, label: "M", title: "Monday" },
        { bit: 1, label: "T", title: "Tuesday" },
        { bit: 2, label: "W", title: "Wednesday" },
        { bit: 3, label: "T", title: "Thursday" },
        { bit: 4, label: "F", title: "Friday" },
        { bit: 5, label: "S", title: "Saturday" },
        { bit: 6, label: "S", title: "Sunday" },
    ];

    get days() {
        return WeekdayMaskField.DAYS;
    }

    get maskValue() {
        // Try every possible way Odoo passes the value
        const val = this.props.value
            ?? (this.props.record && this.props.name
                ? this.props.record.data[this.props.name]
                : undefined)
            ?? 127;
        return val | 0;
    }

    isActive(bit) {
        return Boolean(this.maskValue & (1 << bit));
    }

    get isEditable() {
        // Check all possible readonly indicators
        if (this.props.readonly) return false;
        if (this.props.isReadonly) return false;
        if (this.props.record && this.props.record.isReadonly) return false;
        return true;
    }

    async onToggle(bit) {
        if (!this.isEditable) return;

        const newValue = this.maskValue ^ (1 << bit);

        // Method 1: props.update (standard field prop)
        if (typeof this.props.update === "function") {
            await this.props.update(newValue);
            return;
        }

        // Method 2: record.update (x2many / relational contexts)
        if (this.props.record && this.props.name
            && typeof this.props.record.update === "function") {
            await this.props.record.update({ [this.props.name]: newValue });
            return;
        }

        console.warn("WeekdayMaskField: no update method available", this.props);
    }
}

registry.category("fields").add("weekday_mask", {
    component: WeekdayMaskField,
    supportedTypes: ["integer"],
});