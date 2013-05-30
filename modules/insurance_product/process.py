from trytond.pool import PoolMeta

from trytond.modules.coop_utils import model, fields


__all__ = [
    'ProcessProductRelation',
    'ProcessDesc',
]


class ProcessProductRelation(model.CoopSQL):
    'Process Product Relation'

    __name__ = 'ins_product.process_product_relation'

    product = fields.Many2One('offered.product', 'Product',
        ondelete='CASCADE')
    process = fields.Many2One('process.process_desc', 'Process',
        ondelete='CASCADE')


class ProcessDesc():
    'Process Desc'

    __name__ = 'process.process_desc'
    __metaclass__ = PoolMeta

    for_products = fields.Many2Many('ins_product.process_product_relation',
        'process', 'product', 'Products')
