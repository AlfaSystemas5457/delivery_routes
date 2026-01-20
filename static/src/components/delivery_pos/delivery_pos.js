/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AddressCard } from "../address_card/address_card";
import { CustomerCard } from "../customer_card/customer_card";

export class DeliveryPosView extends Component {
    static template = "delivery_routes.DeliveryPosView";

    static components = { AddressCard, CustomerCard };

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
                ["name", "state", "route_address_ids", "product", "description"],
                { limit: 1 }
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

        // if (this.terminalId) {
        //     const configs = await this.orm.read("delivery.config", [this.terminalId], ["name", "driver_id"]);
        //     this.state.config = configs[0];

        //     const routes = await this.orm.searchRead(
        //         "route.route",
        //         [["user_id", "=", this.state.config.driver_id[0]], ["state", "!=", "end"]],
        //         ["name", "state", "route_address_ids"],
        //         { limit: 1 }
        //     );
        //     this.state.activeRoute = routes.length > 0 ? routes[0] : null;
        // }
        // this.state.isLoading = false;
    }

    async startNewRoute() {
        try {
            const newId = await this.orm.create("route.route", [{}]);

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
                await this.orm.write("route.route", [route.id], { state: "end" });
                this.notification.add("Ruta finalizada correctamente", { type: "success" });
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
        this.state.selectedAddress = address;
    }

    async onCloseAddressDetails() {
        this.state.selectedAddress = null;

        await this._loadData();
    }
}
registry.category("actions").add("delivery_routes.pos_view", DeliveryPosView);