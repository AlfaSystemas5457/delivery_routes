# -*- coding: utf-8 -*-
{
    'name': "Rutas de entrega",

    'summary': "Modulo de rutas de entrega",

    'description': """Modulo de rutas de entrega""",

    'author': "DGV",
    # 'website': "https://www.yourcompany.com",
    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base', 'stock', 'hr', 'sale'],

    'data': [
        'security/ir.model.access.csv',
        # 'security/route_security.xml',
        # 'security/groups_security.xml',
        'views/res_users_views.xml',
        # 'views/res_users_views.xml',
        'views/menu_views.xml',
        'views/route_sale_address_view.xml',
        'views/route_view.xml',
        'views/address_view.xml',
        # 'views/contac_salesperson_view.xml',
    ],
    'installable': True,
    'application': True,
    'sequence': 0,
}
