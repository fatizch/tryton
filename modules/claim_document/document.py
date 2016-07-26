# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast
from sql.functions import Substring
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

from trytond import backend
from trytond.transaction import Transaction


__metaclass__ = PoolMeta
__all__ = [
    'DocumentRequest',
    'RequestFinder',
    'DocumentRequestLine',
    ]


class DocumentRequestLine:
    __name__ = 'document.request.line'

    claim = fields.Many2One('claim', 'Claim', ondelete='CASCADE', select=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table_handler = TableHandler(cls, module_name)
        cursor = Transaction().connection.cursor()
        migrate = False
        # Migrate from 1.8 : add field relation to a claim
        if not table_handler.column_exist('claim'):
            migrate = True
        super(DocumentRequestLine, cls).__register__(module_name)
        if migrate:
            table = cls.__table__()
            cursor.execute(*table.update(
                    columns=[table.claim],
                    values=[Cast(Substring(table.for_object, len('claim,') + 1),
                            cls.claim.sql_type().base)],
                    where=(table.for_object.like('claim,%'))
                    ))


class DocumentRequest:
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by.selection.append(('claim', 'Claim'))
        cls.needed_by.selection.append(
            ('claim.service', 'Claim Service'))


class RequestFinder:
    __name__ = 'document.receive.request'

    @classmethod
    def allowed_values(cls):
        result = super(RequestFinder, cls).allowed_values()
        result.update({'claim': ('Claim', 'name')})
        return result
