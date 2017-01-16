# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.operators import Concat

from trytond.pool import Pool

import address
import party
import test_case


def register():
    Pool.register(
        address.Address,
        party.Party,
        test_case.TestCaseModel,
        module='party_fr', type_='model')

    Pool.register_post_init_hooks(migrate_1_10_include_line3_in_street,
        module='party_fr')


def migrate_1_10_include_line3_in_street(pool):
    from trytond import backend
    from trytond.transaction import Transaction
    from trytond.modules.party import Address

    previous_register = Address.__register__.im_func

    @classmethod
    def patched_register(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)
        sql_table = cls.__table__()
        migrate_name = table.column_exist('streetbis') and \
            table.column_exist('line3')

        previous_register(cls, module_name)

        # Migration from 1.10 : merge line3 into street
        if migrate_name:
            value = Concat(sql_table.line3, Concat('\n', sql_table.street))
            cursor.execute(*sql_table.update([sql_table.street], [value]))
            table.drop_column('line3')

    Address.__register__ = patched_register
