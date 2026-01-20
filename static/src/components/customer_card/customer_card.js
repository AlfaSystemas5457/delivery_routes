/** @odoo-module **/
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CustomerCard extends Component {
    static template = "delivery_routes.CustomerCard";

    static props = {
        address: Object,
        onClose: Function,
        onProductsLoaded: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.localAddress = useState({
            id: this.props.address.id,
            contact: this.props.address.contact,
            address: this.props.address.address,
            status: this.props.address.status,
            product_lines: [],
            currentStep: this.props.address.current_step || 0,
            sale_order_id: this.props.address.sale_order_id,
            sale_details: {},
            sale_order_lines_details: [],
            paymentTerms: [],
        });

        this.statusLabels = {
            pending: 'Pendiente',
            visited: 'Visitado con pedido',
            skipped: 'Visitado sin pedido',
        };

        this.statusSaleOrderLinesLabels = {
            draft: 'Borrador',
            sent: 'Enviado',
            sale: 'Vendido',
            cancel: 'Cancelado',
        };

        this.steps = [
            'Pedido',
            'Venta',
            'Inventario',
            'Pago',
        ];

        onMounted(() => {
            if (!this.localAddress.product_lines.length) {
                this.loadProducts();
            }
        });

        this.availableProducts = useState({ items: [] });

        this.loadProducts();
    }

    handleCloseModal() {
        this.props.onClose?.();
    }

    get progressPercent() {
        const total = this.steps.length || 1;
        const completed = this.localAddress.currentStep + 1 || 0;
        return Math.min(Math.round((completed / total) * 100), 100);
    }

    get canGoNext() {
        return this.localAddress.currentStep < this.steps.length - 1;
    }

    get canGoBack() {
        return this.localAddress.currentStep > 0;
    }

    async loadProducts() {
        try {
            const result = await this.orm.call(
                "route.sale.address",
                "action_load_route_products",
                [[this.localAddress.id]]
            );

            this.localAddress.contact = result.contact;
            this.localAddress.address = result.address;
            this.localAddress.status = result.status;
            this.localAddress.product_lines = result.product_lines;
            this.localAddress.sale_order_id = result.sale_order_id;

            this.props.onProductsLoaded?.(this.props.address.id);
            this.loadAvailableProducts();
            this.getSaleDetails();
            this.loadPaymentTerms();
            // this.notification.add(
            //     "Productos cargados correctamente",
            //     { type: "success" }
            // );
        } catch (error) {
            this.notification.add(
                "Error al cargar productos: " + error.message,
                { type: "danger" }
            );
        }
    }

    async loadAvailableProducts() {
        try {
            const allProducts = await this.orm.call(
                "route.sale.address",
                "get_available_products",
                [[this.localAddress.id]]
            );
            this.availableProducts.items = allProducts || [];
        } catch (error) {
            this.notification.add(
                "Error al cargar productos disponibles: " + error.message,
                { type: "danger" }
            );
        }
    }

    async onQuantityChange(ev, line) {
        const value = parseFloat(ev.target.value) || 0;
        line.quantity = value;
        this.localAddress.product_lines = [...this.localAddress.product_lines];
    }

    async saveProducts() {
        try {
            await this.orm.call(
                "route.sale.address",
                "action_save_product_quantities",
                [[this.localAddress.id], this.localAddress.product_lines]
            );

            this.props.onProductsLoaded?.(this.props.address.id);
            this.notification.add(
                "Cantidades guardadas correctamente",
                { type: "success" }
            );

        } catch (error) {
            this.notification.add(
                "Error al guardar cantidades: " + error.message,
                { type: "danger" }
            );
        }
    }

    async onStatusChange(ev) {
        const newStatus = ev.target.value;

        this.localAddress.status = newStatus;

        try {
            await this.orm.call(
                "route.sale.address",
                "action_update_status",
                [[this.localAddress.id], newStatus]
            );

            this.props.onProductsLoaded?.(this.props.address.id);
            this.notification.add(
                "Estado actualizado",
                { type: "success" }
            );

        } catch (error) {
            this.notification.add(
                "Error al actualizar estado: " + error.message,
                { type: "danger" }
            );
        }
    }

    async onProductSelected(ev) {
        const productId = parseInt(ev.target.value);
        if (productId) {
            this.addProductById(productId);
        }
        this.loadAvailableProducts();
    }

    async addProductById(productId) {
        try {
            if (!productId) return;

            const line = await this.orm.call(
                "route.sale.address",
                "action_add_product_line",
                [[this.localAddress.id], productId]
            );

            this.localAddress.product_lines = [
                ...this.localAddress.product_lines,
                line,
            ];

            this.loadAvailableProducts();
            this.notification.add("Producto agregado", { type: "success" });
        } catch (error) {
            this.notification.add(
                error.message || "Error al agregar producto",
                { type: "danger" }
            );
        }
    }

    async createSaleOrder() {
        try {
            await this.saveProducts();
            const result = await this.orm.call(
                "route.sale.address",
                "handle_button_sale_terminal",
                [[this.localAddress.id]]
            );

            const orderId = result.sale_order_id;
            if (!orderId) {
                throw new Error("No se creó la orden");
            }
            this.localAddress.sale_order_id = orderId;
            this.getSaleDetails();

            this.notification.add(
                "Orden creada correctamente con ID: " + orderId,
                { type: "success" }
            );
            this.nextStep();
        } catch (error) {
            this.notification.add(
                "Error al crear la orden: " + error.message,
                { type: "danger" }
            );
        }
    }

    async getSaleDetails() {
        const orderLineIds = this.localAddress.sale_details.order_line || [];
        if (!Array.isArray(orderLineIds) || orderLineIds.length === 0) {
            this.localAddress.sale_order_lines_details = [];
        }
        if (!this.localAddress.sale_order_id) return;

        const saleOrder = await this.orm.searchRead(
            "sale.order",
            [["id", "=", this.localAddress.sale_order_id]],
            ["name", "partner_id", "payment_term_id", "amount_untaxed", "amount_tax", "amount_total", "order_line", "state"],
            { limit: 1 }
        );

        this.localAddress.sale_details = saleOrder.length > 0 ? saleOrder[0] : {};
        console.log(this.localAddress.sale_details);

        const saleOrderLines = await this.orm.searchRead(
            "sale.order.line",
            [["order_id", "=", this.localAddress.sale_order_id]],
            ["id", "product_id", "product_uom_qty", "price_unit", "price_subtotal"]
        );
        console.log("Sale Order Lines:", saleOrderLines);
        this.localAddress.sale_order_lines_details = saleOrderLines.length > 0 ? saleOrderLines : [];
    }

    async loadPaymentTerms() {
        try {
            const paymentTerms = await this.orm.searchRead(
                "account.payment.term",
                [],
                ["id", "name"]
            );
            this.localAddress.paymentTerms = paymentTerms;
        } catch (error) {
            this.notification.add("Error al cargar términos de pago: " + error.message, { type: "danger" });
        }
    }

    async onPaymentTermChange(ev) {
        const selectedId = parseInt(ev.target.value, 10);
        if (!selectedId) {
            this.localAddress.sale_details.payment_term_id = [];
            return;
        }

        this.localAddress.sale_details.payment_term_id = [selectedId, ev.target.options[ev.target.selectedIndex].text];

        try {
            await this.orm.call(
                "sale.order",
                "write",
                [[this.localAddress.sale_order_id], { payment_term_id: selectedId }]
            );
            this.notification.add("Término de pago actualizado", { type: "success" });
        } catch (error) {
            this.notification.add("Error al actualizar término de pago: " + error.message, { type: "danger" });
        }
    }

    removeLine = async (line) => {
        try {
            await this.orm.call(
                "route.sale.address",
                "action_remove_product_line",
                [[this.localAddress.id], line.id]
            );

            this.localAddress.product_lines = this.localAddress.product_lines.filter(
                l => l.id !== line.id
            );

            this.loadAvailableProducts();
            this.notification.add("Producto eliminado", { type: "success" });
        } catch (error) {
            this.notification.add("Error al eliminar producto: " + error.message, { type: "danger" });
        }
    };

    nextStep = async () => {
        if ((this.localAddress.currentStep + 1) < this.steps.length) {
            this.localAddress.currentStep++;
            await this.orm.call(
                "route.sale.address",
                "write",
                [[this.localAddress.id], { current_step: this.localAddress.currentStep }]
            );
        }
    }

    returnStep = async () => {
        if ((this.localAddress.currentStep - 1) >= 0) {
            this.localAddress.currentStep--;
            await this.orm.call(
                "route.sale.address",
                "write",
                [[this.localAddress.id], { current_step: this.localAddress.currentStep }]
            );
        }
    }
}
