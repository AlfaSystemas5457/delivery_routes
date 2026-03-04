/** @odoo-module **/
import { Component, useState, onMounted, useRef, onPatched, markup } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { LotSelector } from "../lot_selector/lot_selector";

export class CustomerCard extends Component {
    static template = "delivery_routes.CustomerCard";
    static components = { LotSelector, ConfirmationDialog, LotSelector };

    static props = {
        address: Object,
        activeRoute: Object,
        onClose: Function,
        onProductsLoaded: Function,
    };

    setup() {
        this.signatureCanvasRef = useRef("signatureCanvas");
        this.signaturePad = null;
        this.signaturePadTasting = null;
        this.invoiceLinesById = useState([]);
        this.state = useState(
            {
                showSignatureModal: false,
                showSignatureModalTasting: false
            }
        );

        this.orm = useService("orm");
        this.notification = useService("notification");

        this.localAddress = useState(
            {
                // general
                id: this.props.address.id,
                contact: this.props.address.contact,
                address: this.props.address.address,
                status: this.props.address.status,
                currentStep: this.props.address.current_step || 0,

                // producto
                product_lines: [],
                lot_ids: [],
                lists_lot_selected_ids: [],
                selected_line_id: null,
                selected_lot_location_id: null,
                selected_line_move_ids: [],

                // venta
                sale_order_id: this.props.address.sale_order_id,
                sale_details: {},
                sale_order_lines_details: [],
                paymentTerms: [],

                // entrega
                stock_picking_id: false,
                stock_picking_details: {},
                stock_picking_line_details: [],

                // factura
                invoice_ids: [],
                invoice_details: [],

                // devoluciones
                refund_id: false,
                is_refund: false,
                return_lines: [],
                selected_line_id_refund: null,
                selected_line_id_refund_selected_move_line: [],

                // degustaciones
                tasting_id: false,
                is_tasting: false,
                tasting_lines: [],
                selected_line_id_tasting: null,
                selected_line_id_tasting_selected_move_line: [],
            }
        );

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

        this.statusStockPickingLabels = {
            draft: 'Borrador',
            waiting: 'En espera de otra operación',
            confirmed: 'En espera',
            assigned: 'Listo',
            done: 'Hecho',
            cancel: 'Cancelado',
        };

        this.statusInvoiceLabels = {
            draft: 'Borrador',
            posted: 'Registrado',
            cancel: 'Cancelado',
        };

        this.steps = [
            'Pedido',
            'Venta',
            'Inventario',
            'Pago',
        ];

        onPatched(() => {
            this.initSignaturePad();
            this.initSignaturePadTasting();
        });


        onMounted(() => {
            this.loadProducts();
        });

        this.availableProducts = useState({ items: [] });
        this.availableProductsRefund = useState({ items: [] });
        this.availableProductsTasting = useState({ items: [] });
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

    // Lote de Tasting
    async showLotFormTasting(line) {
        try {
            this.localAddress.selected_line_id_tasting = line;
            await this.getStockMoveLineLotsTasting(this.localAddress.selected_line_id_tasting.id);
            console.log(line)
        } catch (error) {
            this.notification.add("Error al mostrar formulario de lotes: " + error.message, { type: "danger" });
        }
    }

    async hideLotFormTasting() {
        try {
            this.localAddress.selected_line_id_tasting = null;
            await this.loadProducts()
        } catch (error) {
            this.notification.add("Error al cerrar formulario de lotes: " + error.message, { type: "danger" });
        }
    }

    getLotNamesForLineTasting(line) {
        if (!line.lot_ids || !this.localAddress.lot_ids) {
            return "";
        }

        return this.localAddress.lot_ids
            .filter(lot => line.lot_ids.includes(lot.id))
            .map(lot => lot.name)
            .join(", ");
    }

    async addLotTasing() {
        try {
            console.log(this.localAddress.selected_line_id_tasting)
            await this.orm.create(
                "route.sale.tasting.move.line",
                [{
                    tasting_line_id: this.localAddress.selected_line_id_tasting.id,
                    product_id: this.localAddress.selected_line_id_tasting.product_id[0],
                    quantity: 0,
                }]
            )
            await this.getStockMoveLineLotsTasting(this.localAddress.selected_line_id_tasting.id);
        } catch (error) {
            this.notification.add("Error al agregar lote: " + error.message, { type: "danger" });
        }
    }

    async getStockMoveLineLotsTasting(id) {
        this.localAddress.selected_line_id_tasting_selected_move_line = await this.orm.searchRead(
            "route.sale.tasting.move.line",
            [["tasting_line_id", "=", id]],
            ["id", "tasting_line_id", "product_id", "lot_id", "quantity"]
        )
        console.log(this.localAddress.selected_line_id_tasting_selected_move_line)
    }

    async onLotLineSelectedTasting(ev, line_lot) {
        try {
            const selectedId = parseInt(ev.id, 10);
            if (!selectedId) return;

            await this.orm.write(
                "route.sale.tasting.move.line",
                [("tasting_line_id", "=", line_lot.id)],
                { lot_id: selectedId }
            );
            await this.getStockMoveLineLotsTasting(this.localAddress.selected_line_id_tasting.id);
        } catch (error) {
            this.notification.add("Error al actualizar el lote: " + error.message, { type: "danger" });
        }
    }

    async onLotQuantityChangeTasting(ev, line_lot) {
        try {
            const value = parseInt(ev.target.value, 10);
            if (!value) return;

            await this.orm.write(
                "route.sale.tasting.move.line",
                [("tasting_line_id", "=", line_lot.id)],
                { quantity: value }
            );
            await this.getStockMoveLineLotsTasting(this.localAddress.selected_line_id_tasting.id);
        } catch (error) {
            this.notification.add("Error al actualizar cantidad del lote: " + error.message, { type: "danger" });
        }
    }

    async removeLotTasting(line) {
        try {
            await this.orm.unlink("route.sale.tasting.move.line", [line.id]);
            await this.getStockMoveLineLotsTasting(this.localAddress.selected_line_id_tasting.id);
        } catch (error) {
            this.notification.add("Error al eliminar lote: " + error.message, { type: "danger" });
        }
    }

    // Lote de Refund
    async showLotFormRefund(line) {
        try {
            this.localAddress.selected_line_id_refund = line;
            await this.getStockMoveLineLotsRefund(this.localAddress.selected_line_id_refund.id);
            console.log(line)
        } catch (error) {
            this.notification.add("Error al mostrar formulario de lotes: " + error.message, { type: "danger" });
        }
    }

    async hideLotFormRefund() {
        try {
            this.localAddress.selected_line_id_refund = null;
            await this.loadProducts()
        } catch (error) {
            this.notification.add("Error al cerrar formulario de lotes: " + error.message, { type: "danger" });
        }
    }

    getLotNamesForLineRefund(line) {
        if (!line.lot_ids || !this.localAddress.lot_ids) {
            return "";
        }

        return this.localAddress.lot_ids
            .filter(lot => line.lot_ids.includes(lot.id))
            .map(lot => lot.name)
            .join(", ");
    }

    async addLotRefund() {
        try {
            console.log(this.localAddress.selected_line_id_refund)
            await this.orm.create(
                "route.sale.return.move.line",
                [{
                    return_line_id: this.localAddress.selected_line_id_refund.id,
                    product_id: this.localAddress.selected_line_id_refund.product_id[0],
                    quantity: 0,
                }]
            )
            await this.getStockMoveLineLotsRefund(this.localAddress.selected_line_id_refund.id);
        } catch (error) {
            this.notification.add("Error al agregar lote: " + error.message, { type: "danger" });
        }
    }

    async getStockMoveLineLotsRefund(id) {
        this.localAddress.selected_line_id_refund_selected_move_line = await this.orm.searchRead(
            "route.sale.return.move.line",
            [["return_line_id", "=", id]],
            ["id", "return_line_id", "product_id", "lot_id", "quantity"]
        )
        console.log(this.localAddress.selected_line_id_refund_selected_move_line)
    }

    async onLotLineSelectedRefund(ev, line_lot) {
        try {
            const selectedId = parseInt(ev.id, 10);
            if (!selectedId) return;

            await this.orm.write(
                "route.sale.return.move.line",
                [("return_line_id", "=", line_lot.id)],
                { lot_id: selectedId }
            );
            await this.getStockMoveLineLotsRefund(this.localAddress.selected_line_id_refund.id);
        } catch (error) {
            this.notification.add("Error al actualizar el lote: " + error.message, { type: "danger" });
        }
    }

    async onLotQuantityChangeRefund(ev, line_lot) {
        try {
            const value = parseInt(ev.target.value, 10);
            if (!value) return;

            await this.orm.write(
                "route.sale.return.move.line",
                [("return_line_id", "=", line_lot.id)],
                { quantity: value }
            );
            await this.getStockMoveLineLotsRefund(this.localAddress.selected_line_id_refund.id);
        } catch (error) {
            this.notification.add("Error al actualizar cantidad del lote: " + error.message, { type: "danger" });
        }
    }

    async removeLotRefund(line) {
        try {
            await this.orm.unlink("route.sale.return.move.line", [line.id]);
            await this.getStockMoveLineLotsRefund(this.localAddress.selected_line_id_refund.id);
        } catch (error) {
            this.notification.add("Error al eliminar lote: " + error.message, { type: "danger" });
        }
    }

    // Lote de inventario
    async addLot() {
        try {
            await this.orm.create(
                "stock.move.line",
                [{
                    move_id: this.localAddress.selected_line_id.id,
                    product_id: this.localAddress.selected_line_id.product_id[0],
                    picking_id: this.localAddress.stock_picking_details.id,
                }]
            )
            await this.getStockMoveLineLots(this.localAddress.selected_line_id.id);
        } catch (error) {
            this.notification.add("Error al agregar lote: " + error.message, { type: "danger" });
        }
    }

    async removeLot(line) {
        try {
            await this.orm.unlink("stock.move.line", [line.id]);
            await this.getStockMoveLineLots(this.localAddress.selected_line_id.id);
        } catch (error) {
            this.notification.add("Error al eliminar lote: " + error.message, { type: "danger" });
        }
    }

    async onLotLineSelected(ev, line_lot) {
        try {
            const selectedId = parseInt(ev.id, 10);
            if (!selectedId) return;

            await this.orm.write(
                "stock.move.line",
                [line_lot.id],
                { lot_id: selectedId }
            );
        } catch (error) {
            this.notification.add("Error al actualizar el lote: " + error.message, { type: "danger" });
        }
    }

    async onLotQuantityChange(ev, line_lot) {
        try {
            const value = parseFloat(ev.target.value) || 0;
            await this.orm.write(
                "stock.move.line",
                [line_lot.id],
                { quantity: value }
            );
        } catch (error) {
            this.notification.add("Error al actualizar cantidad del lote: " + error.message, { type: "danger" });
        }
    }

    async getStockMoveLineLots(id) {
        this.localAddress.selected_line_move_ids = await this.orm.searchRead(
            "stock.move.line",
            [["move_id", "=", id]],
            ["id", "picking_id", "move_id", "product_id", "lot_id", "quantity"]
        )
    }

    async showLotForm(line) {
        try {
            await this.getStockPickingDetails();
            await this.getStockMoveLineLots(line.id);
            this.localAddress.selected_line_id = line;
        } catch (error) {
            this.notification.add("Error al mostrar formulario de lotes: " + error.message, { type: "danger" });
        }
    }

    async hideLotForm() {
        try {
            await this.getStockPickingDetails();
            this.localAddress.selected_line_id = null;
            this.localAddress.selected_line_move_ids = [];
        } catch (error) {
            this.notification.add("Error al cerrar formulario de lotes: " + error.message, { type: "danger" });
        }
    }

    async openMap() {
        try {
            const geo_locateion = await this.orm.call(
                "route.sale.address",
                "get_geolocation",
                [[this.localAddress.id]]
            );

            if (geo_locateion.latitude === 0 && geo_locateion.longitude === 0) {
                this.notification.add(
                    "La dirección no tiene coordenadas geográficas.",
                    { type: "warning" }
                );
                return;
            }

            const latitude = geo_locateion.latitude;
            const longitude = geo_locateion.longitude;
            const url = `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
            window.open(url, '_blank');

        } catch (error) {
            this.notification.add(
                "Error al abrir el mapa: " + error.message,
                { type: "danger" }
            );
        }
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

            this.localAddress.refund_id = result.refund_id;
            this.localAddress.is_refund = result.is_refund;
            this.localAddress.return_lines = result.return_lines;

            this.localAddress.tasting_id = result.tasting_id;
            this.localAddress.is_tasting = result.is_tasting;
            this.localAddress.tasting_lines = result.tasting_lines;

            const productIds = this.localAddress.product_lines.map(line =>
                line.product_id && line.product_id[0]
            ).filter(id => !!id);

            this.localAddress.lot_ids = await this.orm.searchRead(
                "stock.lot",
                [["product_id", "in", productIds]],
                ["id", "name", "product_id", "product_qty"],
            );

            this.props.onProductsLoaded?.(this.props.address.id);
            await this.loadAvailableProducts();
            await this.getSaleDetails();
            await this.loadPaymentTerms();
            await this.getStockPickingDetails();
            await this.getInvoiceDetails();
        } catch (error) {
            this.notification.add(
                "Error al cargar productos: " + error.message,
                { type: "danger" }
            );
        }
    }

    async toggleNoCharge(line) {
        line.no_charge = !line.no_charge;

        try {
            await this.orm.call(
                "route.sale.product.line",
                "write",
                [[line.id], { no_charge: line.no_charge }]
            );
        } catch (error) {
            line.no_charge = !line.no_charge;
            console.error(error);
        }
    }

    async toggleRefund() {
        try {
            this.localAddress.is_refund = !this.localAddress.is_refund;
            await this.orm.call(
                "route.sale.address",
                "write",
                [[this.localAddress.id], { is_refund: this.localAddress.is_refund }]
            );
        } catch (error) {
            this.notification.add(
                "Error al cambiar la devolución: " + error.message,
                { type: "danger" }
            );
        }
    }

    async toggleTasting() {
        try {
            this.localAddress.is_tasting = !this.localAddress.is_tasting;
            await this.orm.call(
                "route.sale.address",
                "write",
                [[this.localAddress.id], { is_tasting: this.localAddress.is_tasting }]
            );
        } catch (error) {
            this.notification.add(
                "Error al cambiar la degustación: " + error.message,
                { type: "danger" }
            );
        }
    }

    getLotNamesForLine(line) {
        if (!line.lot_ids || !this.localAddress.lot_ids) {
            return "";
        }

        return this.localAddress.lot_ids
            .filter(lot => line.lot_ids.includes(lot.id))
            .map(lot => lot.name)
            .join(", ");
    }

    async onLotSelectedRefund(ev, line) {
        try {
            const selectedId = parseInt(ev.target.value, 10);
            if (!selectedId) return;

            line.lot_id = [selectedId, ev.target.options[ev.target.selectedIndex].text];
            this.localAddress.product_lines = [...this.localAddress.product_lines];

            await this.orm.call(
                "route.sale.return.line",
                "write",
                [[line.id], { lot_id: selectedId }]
            );

            this.notification.add("Lote actualizado", { type: "success" });
        } catch (error) {
            console.error(error)
            this.notification.add("Error al actualizar el lote: " + (error.message || error), { type: "danger" });
        }
    }

    async onLotSelectedTasting(ev, line) {
        try {
            const selectedId = parseInt(ev.target.value, 10);
            if (!selectedId) return;

            line.lot_id = [selectedId, ev.target.options[ev.target.selectedIndex].text];
            this.localAddress.product_lines = [...this.localAddress.product_lines];

            await this.orm.call(
                "route.sale.tasting.line",
                "write",
                [[line.id], { lot_id: selectedId }]
            );

            this.notification.add("Lote actualizado", { type: "success" });
        } catch (error) {
            console.error(error)
            this.notification.add("Error al actualizar el lote: " + (error.message || error), { type: "danger" });
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
    async loadAvailableProductsRefund() {
        try {
            const allProducts = await this.orm.call(
                "route.sale.address",
                "get_available_products_refund",
                [[this.localAddress.id]]
            );
            this.availableProductsRefund.items = allProducts || [];
        } catch (error) {
            this.notification.add(
                "Error al cargar productos disponibles: " + error.message,
                { type: "danger" }
            );
        }
    }
    async loadAvailableProductsTasting() {
        try {
            const allProducts = await this.orm.call(
                "route.sale.address",
                "get_available_products_tasting",
                [[this.localAddress.id]]
            );
            this.availableProductsTasting.items = allProducts || [];
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

    async onQuantityChangeRefund(ev, line) {
        const value = parseFloat(ev.target.value) || 0;
        line.quantity = value;
        this.localAddress.return_lines = [...this.localAddress.return_lines];
    }

    async onQuantityChangeTasting(ev, line) {
        const value = parseFloat(ev.target.value) || 0;
        line.quantity = value;
        this.localAddress.tasting_lines = [...this.localAddress.tasting_lines];
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

    async saveProductsRefund() {
        try {
            await this.orm.call(
                "route.sale.address",
                "action_save_product_quantities_refund",
                [[this.localAddress.id], this.localAddress.return_lines]
            );

            this.props.onProductsLoaded?.(this.props.address.id);
        } catch (error) {
            this.notification.add(
                "Error al guardar cantidades: " + error.message,
                { type: "danger" }
            );
        }
    }

    async saveProductsTasting() {
        try {
            await this.orm.call(
                "route.sale.address",
                "action_save_product_quantities_tasting",
                [[this.localAddress.id], this.localAddress.tasting_lines]
            );

            this.props.onProductsLoaded?.(this.props.address.id);
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

    async onProductSelectedRefund(ev) {
        try {
            const productId = parseInt(ev.target.value);
            if (!productId) return;

            const line = await this.orm.call(
                "route.sale.address",
                "action_add_product_line_refund",
                [[this.localAddress.id], productId]
            );

            this.localAddress.return_lines = [
                ...this.localAddress.return_lines,
                line,
            ];

            this.loadAvailableProductsRefund();
            this.notification.add("Producto agregado", { type: "success" });
        } catch (error) {
            this.notification.add(
                error.message || "Error al agregar producto",
                { type: "danger" }
            );
        }
    }

    async onProductSelectedTasting(ev) {
        try {
            const productId = parseInt(ev.target.value);
            if (!productId) return;

            const line = await this.orm.call(
                "route.sale.address",
                "action_add_product_line_tasting",
                [[this.localAddress.id], productId]
            );

            this.localAddress.tasting_lines = [
                ...this.localAddress.tasting_lines,
                line,
            ];

            this.loadAvailableProductsTasting();
            this.notification.add("Producto agregado", { type: "success" });
        } catch (error) {
            this.notification.add(
                error.message || "Error al agregar producto",
                { type: "danger" }
            );
        }
    }

    async create_refund_picking() {
        try {
            await this.saveProductsRefund()

            this.env.services.dialog.add(ConfirmationDialog, {
                title: "Confirmar Devolución",
                body: markup(
                    `<div class="d-flex flex-column">
                        <p class="fs-5 fw-bold m-0 p-0" >¿Desea registrar esta devolución ahora?</p>
                        <div class="alert alert-warning d-inline-block text-center mb-0 mt-3"><i class="fa fa-exclamation-triangle me-2"></i>Esta operación generará movimientos de inventario que <strong>no podrán revertirse o modificarse</strong>. Por favor, verifique los datos antes de continuar.</div>
                    </div>`
                ),
                confirmLabel: "Confirmar",
                cancelLabel: "Descartar",
                confirm: async () => {
                    await this.orm.call(
                        "route.sale.address",
                        "create_return_picking",
                        [[this.localAddress.id]]
                    );

                    this.loadProducts()
                },
                cancel: () => {
                    return;
                },
            });
        } catch (error) {
            this.notification.add("Error al crear devolución: " + error.message, { type: "danger" });
        }
    }

    async create_tasting_picking() {
        try {
            await this.saveProductsTasting()

            if (!this.signaturePadTasting || this.signaturePadTasting.isEmpty()) {
                this.notification.add("Por favor dibuja la firma", { type: "danger" });
                return;
            }

            const dataUrl = this.signaturePadTasting.toDataURL("image/png");
            const base64 = dataUrl.split(",")[1];

            await this.orm.call(
                "route.sale.address",
                "create_tasting_picking",
                [[this.localAddress.id], base64],
            );

            await this.loadProducts()
            await this.closeSignatureModalTasting();
            this.localAddress.selected_line_move_ids_tasting = [];
        } catch (error) {
            this.notification.add("Error al crear devolución: " + error.message, { type: "danger" });
        }
    }

    async onPrintRouteTicket() {
        try {
            const result = await this.orm.call(
                "route.sale.address",
                "get_ticket_pos",
                [[this.localAddress.id]]
            );

            if (!result.ticket_pdf) {
                this.notification.add("No se generó el ticket", { type: "warning" });
                return;
            }

            const blob = this.base64ToBlob(result.ticket_pdf, "application/pdf");
            const url = URL.createObjectURL(blob);

            const isPrintSupported = typeof window.print === "function" && !/Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

            if (!isPrintSupported) {
                const a = document.createElement("a");
                a.href = url;
                a.download = `ticket_${this.localAddress.id}.pdf`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                return;
            }

            const iframe = document.createElement("iframe");
            iframe.style.display = "none";
            iframe.src = url;

            document.body.appendChild(iframe);

            iframe.onload = () => {
                try {
                    iframe.contentWindow.focus();
                    iframe.contentWindow.print();
                } catch (e) {
                    console.error("Error en print:", e);
                }
            };
        } catch (error) {
            this.notification.add("Error al imprimir ticket: " + error.message, { type: "danger" });
        }
    }

    base64ToBlob(base64, type) {
        const binary = atob(base64);
        const array = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            array[i] = binary.charCodeAt(i);
        }
        return new Blob([array], { type });
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

    removeLineRefund = async (line) => {
        try {
            await this.orm.call(
                "route.sale.address",
                "action_remove_product_line_refund",
                [[this.localAddress.id], line.id]
            );

            this.localAddress.return_lines = this.localAddress.return_lines.filter(
                l => l.id !== line.id
            );

            this.loadAvailableProductsRefund();
            this.notification.add("Producto eliminado", { type: "success" });
        } catch (error) {
            this.notification.add("Error al eliminar producto: " + error.message, { type: "danger" });
        }
    };

    removeLineTasting = async (line) => {
        try {
            await this.orm.call(
                "route.sale.address",
                "action_remove_product_line_tasting",
                [[this.localAddress.id], line.id]
            );

            this.localAddress.tasting_lines = this.localAddress.tasting_lines.filter(
                l => l.id !== line.id
            );

            this.loadAvailableProductsTasting();
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

    // Venta
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
                "Orden creada correctamente.",
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
        try {
            const orderLineIds = this.localAddress.sale_details.order_line || [];
            if (!Array.isArray(orderLineIds) || orderLineIds.length === 0) {
                this.localAddress.sale_order_lines_details = [];
            }

            if (!this.localAddress.sale_order_id) {
                return;
            }

            const saleOrder = await this.orm.searchRead(
                "sale.order",
                [["id", "=", this.localAddress.sale_order_id]],
                [
                    "name",
                    "partner_id",
                    "payment_term_id",
                    "amount_untaxed",
                    "amount_tax",
                    "amount_total",
                    "order_line",
                    "state",
                ],
                { limit: 1 }
            );

            this.localAddress.sale_details = saleOrder.length > 0 ? saleOrder[0] : {};

            const saleOrderLines = await this.orm.searchRead(
                "sale.order.line",
                [["order_id", "=", this.localAddress.sale_order_id]],
                ["id", "product_id", "product_uom_qty", "price_unit", "price_subtotal"]
            );

            this.localAddress.sale_order_lines_details =
                saleOrderLines.length > 0 ? saleOrderLines : [];
        } catch (error) {
            this.notification.add("Error al cargar detalles de la venta: " + (error.message || error), { type: "danger" });
        }
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
        try {
            const selectedId = parseInt(ev.target.value, 10);
            if (!selectedId) {
                this.localAddress.sale_details.payment_term_id = [];
                return;
            }

            this.localAddress.sale_details.payment_term_id = [selectedId, ev.target.options[ev.target.selectedIndex].text];

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

    async confirmSaleOrder() {
        try {
            if (this.localAddress.sale_details.state === 'draft' || this.localAddress.sale_details.state === 'sent') {
                await this.orm.call(
                    "sale.order",
                    "action_confirm",
                    [[this.localAddress.sale_order_id]]
                );
            }

            await this.getSaleDetails();
            await this.getStockPickingDetails();
            this.notification.add("Orden confirmada", { type: "success" });
            this.nextStep();
        } catch (error) {
            this.notification.add("Error al confirmar orden: " + error.message, { type: "danger" });
        }
    }

    // Inventario
    async onPrintDeliveryTicket() {
        try {
            const result = await this.orm.call(
                "stock.picking",
                "get_delivery_ticket_pdf",
                [[this.localAddress.stock_picking_id]]
            );

            if (!result.ticket_pdf) {
                this.notification.add(
                    "No hay ticket de entrega para imprimir",
                    { type: "warning" }
                );
                return;
            }

            const blob = this.base64ToBlob(result.ticket_pdf, "application/pdf");
            const url = URL.createObjectURL(blob);

            const isPrintSupported = typeof window.print === "function" && !/Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

            if (!isPrintSupported) {
                const a = document.createElement("a");
                a.href = url;
                a.download = `ticket_${this.localAddress.id}.pdf`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                return;
            }

            const iframe = document.createElement("iframe");
            iframe.style.display = "none";
            iframe.src = url;
            document.body.appendChild(iframe);

            iframe.onload = () => {
                iframe.contentWindow.print();
            };
        } catch (error) {
            this.notification.add(
                "Error al generar ticket de entrega: " + error.message,
                { type: "danger" }
            );
        }
    }

    async getStockPickingDetails() {
        try {
            if (this.localAddress.sale_details.state !== "sale") return;

            const pickings = await this.orm.searchRead(
                "stock.picking",
                [["sale_id", "=", this.localAddress.sale_details.id]],
                ["id", "name", "state", "move_ids", "customer_signature"],
                { limit: 1 }
            );

            this.localAddress.stock_picking_details = pickings.length > 0 ? pickings[0] : {};
            this.localAddress.stock_picking_id = this.localAddress.stock_picking_details.id || false;

            const stock_moves = await this.orm.searchRead(
                "stock.move",
                [["picking_id", "=", this.localAddress.stock_picking_details.id]],
                ["id", "product_id", "product_uom_qty", "quantity", "lot_ids"]
            );
            this.localAddress.stock_picking_line_details = stock_moves.length > 0 ? stock_moves : [];
        } catch (error) {
            this.notification.add("Error al cargar detalles de inventario: " + error.message, { type: "danger" });
        }
    }

    scheduleInitSignaturePad() {
        this.env.bus.trigger("owl.nextTick").then(() => {
            this.initSignaturePad();
        });
    }

    openSignatureModal() {
        this.state.showSignatureModal = true;
    }

    initSignaturePad() {
        const canvas = this.signatureCanvasRef.el;
        if (canvas) {
            canvas.width = canvas.offsetWidth;
            canvas.height = canvas.offsetHeight;
            this.signaturePad = new SignaturePad(canvas, {
                penColor: "rgb(0,0,139)",
                backgroundColor: "rgba(255,255,255,0)",
                minWidth: 2.5,
                maxWidth: 2.5,
            });
        }
    }

    clearSignature() {
        if (this.signaturePad) {
            this.signaturePad.clear();
        }
    }

    closeSignatureModal() {
        this.state.showSignatureModal = false;
    }

    scheduleInitSignaturePadTasting() {
        this.env.bus.trigger("owl.nextTick").then(() => {
            this.initSignaturePadTasting();
        });
    }

    openSignatureModalTasting() {
        this.state.showSignatureModalTasting = true;
    }

    initSignaturePadTasting() {
        const canvas = this.signatureCanvasRef.el;
        if (canvas) {
            canvas.width = canvas.offsetWidth;
            canvas.height = canvas.offsetHeight;
            this.signaturePadTasting = new SignaturePad(canvas, {
                penColor: "rgb(0,0,139)",
                backgroundColor: "rgba(255,255,255,0)",
                minWidth: 2.5,
                maxWidth: 2.5,
            });
        }
    }

    clearSignatureTasting() {
        if (this.signaturePadTasting) {
            this.signaturePadTasting.clear();
        }
    }

    closeSignatureModalTasting() {
        this.state.showSignatureModalTasting = false;
    }

    async saveSignature() {
        try {
            if (!this.signaturePad || this.signaturePad.isEmpty()) {
                this.notification.add("Por favor dibuja la firma", { type: "danger" });
                return;
            }

            const dataUrl = this.signaturePad.toDataURL("image/png");
            const base64 = dataUrl.split(",")[1];

            await this.orm.write(
                "stock.picking",
                [this.localAddress.stock_picking_id],
                { customer_signature: base64 }
            );

            this.notification.add("Firma guardada", { type: "success" });
            await this.closeSignatureModal();
            await this.getStockPickingDetails();
        } catch (error) {
            console.warn(error);
            this.notification.add("Error al guardar la firma: " + error.message, { type: "danger" });
        }
    }

    async confirmStockPicking() {
        try {
            await this.orm.call(
                "stock.picking",
                "button_validate",
                [[this.localAddress.stock_picking_id]]
            );
            this.notification.add("Entrega confirmada", { type: "success" });
            this.getStockPickingDetails();
            this.nextStep();
        } catch (error) {
            this.notification.add("Error al confirmar entrega: " + error.message, { type: "danger" });
        }
    }

    // Factura
    onPrintInvoiceTicket = async (invoiceId) => {
        try {
            const result = await this.orm.call(
                "account.move",
                "get_invoice_ticket_pdf",
                [[invoiceId]]
            );

            if (!result.ticket_pdf) {
                this.notification.add("No hay ticket de factura para imprimir", { type: "warning" });
                return;
            }

            const blob = this.base64ToBlob(result.ticket_pdf, "application/pdf");
            const url = URL.createObjectURL(blob);

            const isPrintSupported = typeof window.print === "function" && !/Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

            if (!isPrintSupported) {
                const a = document.createElement("a");
                a.href = url;
                a.download = `ticket_${this.localAddress.id}.pdf`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                return;
            }

            const iframe = document.createElement("iframe");
            iframe.style.display = "none";
            iframe.src = url;
            document.body.appendChild(iframe);

            iframe.onload = () => {
                iframe.contentWindow.print();
            };
        } catch (error) {
            this.notification.add("Error al imprimir ticket de factura: " + error.message, { type: "danger" });
        }
    }

    async createInvoice() {
        try {
            const invoiceIds = await this.orm.call(
                "sale.order",
                "action_create_invoice_rpc",
                [[this.localAddress.sale_order_id]],
                {}
            );

            if (invoiceIds && invoiceIds.length) {
                this.localAddress.invoice_ids = invoiceIds;

                await this.getInvoiceDetails();

                this.notification.add("Factura creada correctamente", { type: "success" });
            } else {
                this.notification.add("No se generó ninguna factura", { type: "warning" });
            }
        } catch (error) {
            this.notification.add("Error al crear factura: " + (error.message || error), { type: "danger" });
        }
    }

    async getInvoiceDetails() {
        try {
            this.localAddress.invoice_ids = await this.orm.call(
                "sale.order",
                "get_invoices_rpc",
                [[this.localAddress.sale_order_id]],
                {}
            );

            if (!this.localAddress.invoice_ids || this.localAddress.invoice_ids.length === 0) {
                this.localAddress.invoice_details = [];
                return;
            }

            const invoices = await this.orm.searchRead(
                "account.move",
                [
                    ["id", "in", this.localAddress.invoice_ids],
                    ["state", "!=", "cancel"]
                ],
                [
                    "id",
                    "name",
                    "amount_untaxed",
                    "amount_tax",
                    "amount_total",
                    "state"
                ]
            );
            this.localAddress.invoice_details = invoices;

            await Promise.all(
                this.localAddress.invoice_details.map(inv => this.loadLinesForInvoice(inv.id))
            );
        } catch (error) {
            this.notification.add("Error al cargar detalles de la factura: " + (error.message || error), { type: "danger" });
        }
    }

    async loadLinesForInvoice(invoiceId) {
        const lines = await this.orm.searchRead(
            "account.move.line",
            [
                ["move_id", "=", invoiceId],
                ["display_type", "=", "product"]
            ],
            [
                "id",
                "product_id",
                "quantity",
                "price_unit",
                "price_subtotal"
            ]
        );
        this.invoiceLinesById[invoiceId] = lines;
    }

    confirmInvoice = async (invoiceId) => {
        try {
            await this.orm.call(
                "account.move",
                "action_post",
                [[invoiceId]],
                {}
            );
            this.notification.add("Factura confirmada", { type: "success" });
            await this.getInvoiceDetails();
        } catch (error) {
            this.notification.add("Error al confirmar factura: " + (error.message || error), { type: "danger" });
        }
    }
}