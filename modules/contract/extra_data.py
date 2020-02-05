# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta

from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields


class ExtraData(metaclass=PoolMeta):
    __name__ = 'extra_data'

    used_by_api = fields.Selection([
            ('', ''),
            ('simulation', 'Simulation'),
            ('quote_creation', 'Quote creation'),
            ('activation', 'Activation'),
            ], 'Used by API',
            states={'invisible': ~Eval('kind').in_([
                    'contract', 'product', 'party_person', 'party_company',
                    'package', 'option', 'covered_element'])})

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        do_migrate = False
        table_handler = TableHandler(cls)
        if not table_handler.column_exist('used_by_api'):
            do_migrate = True
        super(ExtraData, cls).__register__(module_name)
        if not do_migrate:
            return
        table = cls.__table__()
        cursor.execute(*table.update(columns=[table.used_by_api],
            values=['simulation'], where=(
                table.kind.in_(['contract', 'product', 'party_person',
                'party_company', 'package', 'option', 'covered_element']))))
