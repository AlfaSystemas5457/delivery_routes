/** @odoo-module **/
import { Component, useState, onMounted, useRef, onWillUpdateProps } from "@odoo/owl";

export class LotSelector extends Component {
    static template = "delivery_routes.LotSelector";

    static props = {
        lots: { type: Array, optional: true },
        productId: { type: Number, optional: true },
        value: { type: String, optional: true },
        onSelect: Function,
        placeholder: { type: String, optional: true },
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({
            searchTerm: this.props.value || "",
            showDropdown: false,
        });
        this.root = useRef("root");

        // Sincronizar el input si el valor cambia desde el padre
        onWillUpdateProps((nextProps) => {
            if (nextProps.value !== this.props.value) {
                this.state.searchTerm = nextProps.value || "";
            }
        });

        onMounted(() => {
            const onClickOutside = (ev) => {
                // Validación de seguridad para asegurar que el ref existe
                if (this.root.el && !this.root.el.contains(ev.target)) {
                    this.state.showDropdown = false;
                }
            };
            window.addEventListener("click", onClickOutside);
            return () => window.removeEventListener("click", onClickOutside);
        });
    }

    get filteredLots() {
        const query = (this.state.searchTerm || "").toLowerCase();
        const allLots = this.props.lots || [];

        return allLots.filter(lot => {
            const matchProduct = lot.product_id && lot.product_id[0] === this.props.productId;
            const matchQuery = lot.name && lot.name.toLowerCase().includes(query);
            return matchProduct && matchQuery;
        });
    }

    onInput(ev) {
        this.state.searchTerm = ev.target.value;
        this.state.showDropdown = true;
    }

    selectLot(lot) {
        this.state.searchTerm = lot.name;
        this.state.showDropdown = false;
        // Pasamos el objeto lot completo al padre
        this.props.onSelect(lot);
    }
}