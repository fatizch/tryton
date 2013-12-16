from trytond.pool import PoolMeta

from trytond.modules.coop_utils import model, fields


__all__ = [
    'ProcessProductRelation',
    'ProcessDesc',
]


class ProcessProductRelation(model.CoopSQL):
    'Process Product Relation'

    __name__ = 'process-offered.product'

    product = fields.Many2One('offered.product', 'Product',
        ondelete='CASCADE')
    process = fields.Many2One('process', 'Process',
        ondelete='CASCADE')


class ProcessDesc():
    'Process Desc'

    __name__ = 'process'
    __metaclass__ = PoolMeta

    for_products = fields.Many2Many('process-offered.product',
        'process', 'product', 'Products')
