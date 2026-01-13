from odoo import fields, models, api


class ResUsers(models.Model):
    _inherit = "res.users"

    access_scope = fields.Selection(
        [
            ("all", "Mostrar todas las rutas"),
            ("assigned", "Solo mostrar rutas asignadas / propias"),
        ],
        string="Acceso a las rutas",
        default="assigned",
        required=True,
        store=True,
    )

    def _update_groups_based_on_scope(self):
        group_assigned = self.env.ref(
            "delivery_routes.group_route_access_assigned", raise_if_not_found=False
        )
        group_all = self.env.ref(
            "delivery_routes.group_route_access_all", raise_if_not_found=False
        )

        for user in self:
            if not group_assigned or not group_all:
                continue

            # Limpiar grupos
            user.group_ids = user.group_ids - group_assigned - group_all

            # Asignar grupo adecuado
            if user.access_scope == "assigned":
                user.group_ids = user.group_ids | group_assigned
            else:
                user.group_ids = user.group_ids | group_all

    def _update_users_access_scope(self):
        users = self.search([])
        for user in users:
            if user.access_scope == "assigned":
                user._update_groups_based_on_scope()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "access_scope" not in vals:
                vals["access_scope"] = "assigned"

        users = super().create(vals_list)
        users._update_groups_based_on_scope()
        return users

    def write(self, vals):
        res = super().write(vals)
        if "access_scope" in vals:
            self._update_groups_based_on_scope()
        return res
