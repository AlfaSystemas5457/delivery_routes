/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AddressCard } from "../address_card/address_card";
import { CustomerCard } from "../customer_card/customer_card";

export class DeliveryPosView extends Component {
    static template = "delivery_routes.DeliveryPosView";
    static components = { AddressCard, CustomerCard };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            config: null,
            activeRoute: null,
            isLoading: true,
            route_address_ids: [],
            product_ids: [],
            selectedAddress: null,
        });

        this.stateLabels = {
            'start': 'Sin empezar',
            'process': 'En proceso',
            'end': 'Finalizado'
        };

        this.terminalId = this.props.action.context.active_id;

        onWillStart(async () => {
            await this._loadData();
        });
    }

    async _loadData() {
        if (this.terminalId) {
            const configs = await this.orm.read("delivery.config", [this.terminalId], ["name", "driver_id"]);
            this.state.config = configs[0];

            const routes = await this.orm.searchRead(
                "route.route",
                [["user_id", "=", this.state.config.driver_id[0]], ["state", "!=", "end"]],
                ["id", "name", "state", "route_address_ids", "product", "description", "amount_total", "warehouse_id"],
                {
                    limit: 1,
                    order: "id desc"
                }
            );

            if (routes.length > 0) {
                this.state.activeRoute = routes[0];

                if (this.state.activeRoute && this.state.activeRoute.route_address_ids.length > 0) {
                    this.state.route_address_ids = await this.orm.read(
                        "route.sale.address",
                        this.state.activeRoute.route_address_ids,
                        ["contact", "address", "status", "route_id", "product_lines", "sale_order_id", "current_step"]
                    );
                }

                if (this.state.activeRoute && this.state.activeRoute.product.length > 0) {
                    this.state.product_ids = await this.orm.read(
                        "product.product",
                        this.state.activeRoute.product,
                        ["display_name"]
                    );
                }
            }
        }
        this.state.isLoading = false;
    }

    async startNewRoute() {
        try {
            await this.orm.create("route.route", [{}]);

            this.notification.add("Ruta creada correctamente", { type: "success" });
            await this._loadData();
        } catch (error) {
            this.notification.add("Error al iniciar ruta: " + error.message, { type: "danger" });
        }
    }

    async handleActionStart() {
        try {
            if (this.state.activeRoute) {
                const route = this.state.activeRoute;
                await this.orm.write("route.route", [route.id], { state: "process" });
                this.notification.add("Ruta iniciada correctamente", { type: "success" });
                await this._loadData();
            }
        } catch (error) {
            this.notification.add("Error al iniciar ruta: " + error.message, { type: "danger" });
        }
    }

    async handleActionEnd() {
        try {
            if (this.state.activeRoute) {
                const route = this.state.activeRoute;
                await this.onPrintRouteCashOut();
                await this.orm.call(
                    "route.route",
                    "action_end",
                    [[route.id]]
                );
                this.notification.add("Ruta finalizada correctamente", { type: "success" });
                this.state.activeRoute = null;
                await this._loadData();
            }
        } catch (error) {
            this.notification.add("Error al finalizar ruta: " + error.message, { type: "danger" });
        }
    }

    async closeTerminal() {
        window.history.back();
    }

    async reloadAddress(addressId) {
        const updated = await this.orm.read(
            "route.sale.address",
            [addressId],
            ["contact", "address", "status", "product_lines"]
        );
        this.state.route_address_ids =
            this.state.route_address_ids.map(addr =>
                addr.id === addressId ? updated[0] : addr
            );
    }

    async handleProductsLoaded() {
        await this._loadData();
    }

    onSelectAddress(address) {
        if (this.state.activeRoute.state !== 'process') {
            alert('No se ha iniciado la ruta.');
            return;
        }
        this.state.selectedAddress = address;
    }

    async onDeleteAddress(address) {
        try {
            await this.orm.unlink("route.sale.address", [address.id]);
            this.notification.add("Dirección eliminada correctamente", { type: "success" });
            await this._loadData();
        } catch (error) {
            this.notification.add("Error al eliminar la dirección: " + error.message, { type: "danger" });
        }

    }

    async onCloseAddressDetails() {
        this.state.selectedAddress = null;

        await this._loadData();
    }

    base64ToBlob(base64, type) {
        const binary = atob(base64);
        const array = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            array[i] = binary.charCodeAt(i);
        }
        return new Blob([array], { type });
    }

    async onPrintRouteCashOut() {
        try {
            const result = await this.orm.call(
                "route.route",
                "get_cash_out_report",
                [[this.state.activeRoute.id]]
            );

            if (!result.ticket_pdf) {
                this.notification.add("No se generó el reporte", { type: "warning" });
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
            this.notification.add("Error al imprimir reporte: " + error.message, { type: "danger" });
        }
    }
}
registry.category("actions").add("delivery_routes.pos_view", DeliveryPosView);