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

    get progressPercent() {
        const steps = ["Pedido", "Venta", "Inventario", "Pago"];
        const total = steps.length || 1;

        const completed = (this.props.address.current_step ?? 0) + 1;

        return Math.min(Math.round((completed / total) * 100), 100);
    }
}