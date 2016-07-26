# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast
from sql.functions import Substring
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields
from trytond import backend
from trytond.transaction import Transaction


__all__ = [
    'DocumentRequest',
    'DocumentReceiveRequest',
    'DocumentRequestLine',
    ]


class DocumentRequestLine:
    __metaclass__ = PoolMeta
    __name__ = 'document.request.line'

    contract = fields.Many2One('contract', 'Contract',
        ondelete='CASCADE', select=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table_handler = TableHandler(cls, module_name)
        cursor = Transaction().connection.cursor()
        migrate = False
        if not table_handler.column_exist('contract'):
            migrate = True
        # Migrate from 1.8 : add field relation to a contract
        super(DocumentRequestLine, cls).__register__(module_name)
        if migrate:
            table = cls.__table__()
            cursor.execute(*table.update(
                    columns=[table.contract],
                    values=[Cast(Substring(table.for_object,
                                len('contract,') + 1),
                            cls.contract.sql_type().base)],
                    where=(table.for_object.like('contract,%'))
                    ))


class DocumentRequest:
    __metaclass__ = PoolMeta
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by.selection.append(
            ('contract', 'Contract'))


class DocumentReceiveRequest:
    __metaclass__ = PoolMeta
    __name__ = 'document.receive.request'

    @classmethod
    def allowed_values(cls):
        result = super(DocumentReceiveRequest, cls).allowed_values()
        result.update({'contract': ('Contract', 'contract_number')})
        return result
