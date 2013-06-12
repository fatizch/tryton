from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields, utils

__all__ = [
    'Contract',
    ]


class Contract():
    'Contract'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

    dist_network = fields.Many2One('distribution.dist_network',
        'Distribution Network')
    com_product = fields.Function(
        fields.Many2One('distribution.commercial_product',
            'Commercial Product'),
        'get_com_product_id')

    def get_com_product_id(self, name):
        if not self.dist_network:
            return None
        com_products = utils.get_good_versions_at_date(self.dist_network,
            'commercial_products', self.start_date)
        com_product = [x for x in com_products if x.product == self.offered]
        if com_product:
            return com_product[0].id

    def get_dist_network(self):
        return self.dist_network
