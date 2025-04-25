from odoo import fields, models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    access_scope = fields.Selection([
        ('all', 'Mostrar todas las rutas'),
        ('assigned', 'Solo mostrar rutas asignadas / propias')
    ], string="Acceso a las rutas", default='assigned', required=True, store=True)

    def _update_groups_based_on_scope(self):
        group_assigned = self.env.ref(
            'delivery_routes.group_route_access_assigned', raise_if_not_found=False)
        group_all = self.env.ref(
            'delivery_routes.group_route_access_all', raise_if_not_found=False)

        for user in self:
            if not group_assigned or not group_all:
                continue

            # Limpiar grupos
            user.groups_id = user.groups_id - group_assigned - group_all

            # Asignar grupo adecuado
            if user.access_scope == 'assigned':
                user.groups_id = user.groups_id | group_assigned
            else:
                user.groups_id = user.groups_id | group_all

    def create(self, vals_list):
        users = super().create(vals_list)
        users._update_groups_based_on_scope()
        return users

    def write(self, vals):
        res = super().write(vals)
        if 'access_scope' in vals:
            self._update_groups_based_on_scope()
        return res
