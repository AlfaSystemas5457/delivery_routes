/** @odoo-module **/
import { Component } from "@odoo/owl";

export class AddressCard extends Component {
    static template = "delivery_routes.AddressCard";

    static props = {
        address: Object,
        onClick: Function,
    };

    get statusLabel() {
        const labels = {
            'pending': 'Pendiente',
            'visited': 'Visitado con pedido',
            'skipped': 'Visitado sin pedido'
        };
        return labels[this.props.address.status] || 'Desconocido';
    }
}