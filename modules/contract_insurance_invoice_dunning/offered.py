# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Product'
    ]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    dunning_procedure = fields.Many2One('account.dunning.procedure',
        'Dunning Procedure', ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {'dunning_procedure'}
