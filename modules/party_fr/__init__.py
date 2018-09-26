# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from sql.operators import Concat
from sql.conditionals import Coalesce

from trytond.pool import Pool

import address
import party


def register():
    Pool.register(
        address.Address,
        address.Zip,
        party.Party,
        module='party_fr', type_='model')

    Pool.register_post_init_hooks(migrate_1_10_include_line3_in_street,
        module='party')


def migrate_1_10_include_line3_in_street(pool, update):
    if update != 'party':
        return

    from trytond import backend
    from trytond.transaction import Transaction
    from trytond.modules.party.address import Address

    logging.getLogger('modules').info('Running post init hook %s' %
        'migrate_1_10_include_line3_in_street')
    previous_register = Address.__register__.im_func

    @classmethod
    def patched_register(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)
        sql_table = cls.__table__()
        migrate_name = table.column_exist('streetbis') and \
            table.column_exist('line3')

        # Migration from 1.10 : merge line3 into street
        if migrate_name:
            value = Concat(Coalesce(sql_table.line3, ''),
                Concat('\n', Coalesce(sql_table.street, '')))
            cursor.execute(*sql_table.update([sql_table.street], [value]))
            table.drop_column('line3')

        previous_register(cls, module_name)

    Address.__register__ = patched_register
