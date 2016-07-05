# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import os

from trytond.config import config
from trytond.pool import Pool
from trytond.cache import Cache
from trytond.transaction import Transaction

if len(sys.argv) != 2:
    print "Please provide database name as argument"
    sys.exit()
else:
    dbname = sys.argv[1]

config.update_etc(os.path.abspath(os.path.join(os.path.normpath(__file__),
        '..', '..', '..', '..', 'conf', 'trytond.conf')))

CONTEXT = {}

DIMENSION_MAX = int(config.get('table', 'table_dimension', default=4))


def migrate_age_from_value_to_range():
    Pool.start()
    pool = Pool(dbname)
    Cache.clean(dbname)
    with Transaction().start(dbname, 0, context=CONTEXT):
        pool.init()

    with Transaction().start(dbname, 0, context=CONTEXT):
        user_obj = pool.get('res.user')
        user = user_obj.search([('login', '=', 'admin')], limit=1)[0]
        user_id = user.id

    with Transaction().start(dbname, user_id, context=CONTEXT) as transaction:
        TableDefinition = pool.get('table')
        TableDefDim = pool.get('table.dimension.value')

        table_def_dims = TableDefDim.search([], order=[('value', 'ASC')])

        for i in range(1, DIMENSION_MAX + 1):
            table_defs = TableDefinition.search(['AND',
                        ('dimension_name%s' % i, 'in', ['Age', 'age']),
                        ],)
            good_table_defs = [x for x in table_defs
                    if getattr(x, 'dimension_kind%s' % i) == 'value']
            for good_table_def in good_table_defs:
                good_table_def_dims = [x for x in table_def_dims
                        if x.type == 'dimension%s' % i and
                        x.definition.id == good_table_def.id]
                TableDefinition.write([good_table_def], {
                    'dimension_kind%s' % i: 'range',
                    })
                for j in range(len(good_table_def_dims)):
                    if j == 0:
                        TableDefDim.write([good_table_def_dims[j]], {
                                'end': good_table_def_dims[j + 1].value,
                                })
                    elif j == (len(good_table_def_dims) - 1):
                        TableDefDim.write([good_table_def_dims[j]], {
                                'start': good_table_def_dims[j].value,
                                })
                    else:
                        TableDefDim.write([good_table_def_dims[j]], {
                                'start': good_table_def_dims[j].value,
                                'end': good_table_def_dims[j + 1].value,
                                })
                    TableDefDim.write([good_table_def_dims[j]], {
                            'value': None,
                            })

        transaction.commit()


if __name__ == "__main__":
    migrate_age_from_value_to_range()
