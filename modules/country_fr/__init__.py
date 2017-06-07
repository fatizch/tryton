# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool

import country


def register():
    Pool.register(
        country.Zip,
        module='country_fr', type_='model')

    Pool.register_post_init_hooks(migrate_1_12_remove_zip_constraint,
        module='country_cog')


def migrate_1_12_remove_zip_constraint(pool, update):
    Module = pool.get('ir.module')
    country_cog = Module.search([('name', '=', 'country_cog'),
            ('state', 'in', ('to upgrade', 'to activate', 'activated'))])
    if not country_cog:
        return

    Zip = pool.get('country.zip')
    new_constraints = []
    for x in Zip._sql_constraints:
        if x[0] == 'zip_uniq':
            logging.getLogger('modules').info('Running post init hook %s' %
                'migrate_1_12_remove_zip_contraint')
            continue
        new_constraints.append(x)
    Zip._sql_constraints = new_constraints
