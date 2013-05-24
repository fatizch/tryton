from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.modules.coop_utils import model, fields, utils, coop_string

__all__ = [
    'DistributionNetwork',
    'CommercialProduct',
    'DistributionNetworkComProductRelation',
    ]


class DistributionNetwork():
    'Distribution Network'

    __name__ = 'distribution.dist_network'
    __metaclass__ = PoolMeta

    commercial_products = fields.Many2Many(
        'distribution.dist_network-com_product', 'dist_network', 'com_product',
        'Commercial Products')
    top_level_com_products = fields.Function(
        fields.Many2Many('distribution.commercial_product', None, None,
            'Top Level Commercial Products'),
        'get_top_level_com_products_id')

    def get_top_level_com_products(self):
        res = []
        if self.commercial_products:
            res.extend(self.commercial_products)
        if self.top_level:
            res.extend(self.top_level.get_top_level_com_products())
        return res

    def get_top_level_com_products_id(self, name):
        if self.top_level:
            return [x.id for x in self.top_level.get_top_level_com_products()]
        else:
            return []


class CommercialProduct(model.CoopSQL, model.CoopView):
    'Commercial Product'

    __name__ = 'distribution.commercial_product'

    product = fields.Many2One('ins_product.product', 'Technical Product',
        domain=[('start_date', '<=', Eval('start_date'))],
        depends=['start_date'])
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, on_change_with=['name', 'code'])

    @staticmethod
    def default_start_date():
        return utils.today()

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


class DistributionNetworkComProductRelation(model.CoopSQL):
    'Relation Distribution Network - Commercial Product'

    __name__ = 'distribution.dist_network-com_product'

    dist_network = fields.Many2One('distribution.dist_network',
        'Distribution Network', ondelete='CASCADE')
    com_product = fields.Many2One('distribution.commercial_product',
        'Commercial Product', ondelete='RESTRICT')
