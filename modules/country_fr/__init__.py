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

    logging.getLogger('modules').info('Running post init hook %s' %
        'migrate_1_12_remove_zip_contraint')

    Zip = pool.get('country.zip')
    Zip._sql_constraints = [x for x in Zip._sql_constraints
        if x[0] is not 'zip_uniq']
