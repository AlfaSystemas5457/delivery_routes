from odoo.api import Environment, SUPERUSER_ID


def post_init_hook(env):
    users = env['res.users'].search([])
    users._update_groups_based_on_scope()
