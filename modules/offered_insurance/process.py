# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.cog_utils import model, fields


__metaclass__ = PoolMeta
__all__ = [
    'ProcessProductRelation',
    'Process',
    ]


class ProcessProductRelation(model.CoopSQL):
    'Process Product Relation'

    __name__ = 'process-offered.product'

    product = fields.Many2One('offered.product', 'Product',
        ondelete='CASCADE')
    process = fields.Many2One('process', 'Process',
        ondelete='CASCADE')


class Process:
    __name__ = 'process'

    for_products = fields.Many2Many('process-offered.product',
        'process', 'product', 'Products')

    @classmethod
    def _export_skips(cls):
        return (super(Process, cls)._export_skips() | set(['for_products']))
