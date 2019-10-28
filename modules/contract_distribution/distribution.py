# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.cache import Cache
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If

from trytond.modules.coog_core import model, fields, utils

__all__ = [
    'DistributionNetwork',
    'CommercialProduct',
    'DistributionNetworkComProductRelation',
    ]


class DistributionNetwork(metaclass=PoolMeta):
    __name__ = 'distribution.network'

    is_distributor = fields.Boolean('Distributor',
        help='If not checked, this distribution network will not be selectable'
        ' during subscription process.')
    commercial_products = fields.Many2Many(
        'distribution.network-commercial_product', 'dist_network',
        'com_product', 'Commercial Products', depends=['company'], domain=[
            ('product.company', '=', Eval('company'))])
    parent_com_products = fields.Function(
        fields.Many2Many('distribution.commercial_product', None, None,
            'Top Level Commercial Products'),
        'get_parent_com_products_id')
    all_com_products = fields.Function(
        fields.Many2Many('distribution.commercial_product', None, None,
            'All Commercial Products'),
        'get_all_commercial_products_id')
    distributors = fields.Function(
        fields.Many2Many('distribution.network', None, None, 'Distributors',
            help='All distributors "below" this network'),
        'getter_distributors')

    _get_all_distributors_cache = Cache('get_all_distributors')

    @classmethod
    def create(cls, vlist):
        created = super(DistributionNetwork, cls).create(vlist)
        cls._get_all_distributors_cache.clear()
        return created

    @classmethod
    def delete(cls, ids):
        super(DistributionNetwork, cls).delete(ids)
        cls._get_all_distributors_cache.clear()

    @classmethod
    def write(cls, *args):
        super(DistributionNetwork, cls).write(*args)
        cls._get_all_distributors_cache.clear()

    def get_parent_com_products_id(self, name):
        ComProduct = Pool().get('distribution.commercial_product')
        return [x.id for x in ComProduct.search([('dist_networks', 'where',
                            [('left', '<', self.left),
                                ('right', '>', self.right), ]), ])]

    def get_all_commercial_products_id(self, name):
        return [x.id for x in set(
                self.commercial_products + self.parent_com_products)]

    def getter_distributors(self, name):
        return [x.id for x in self.search([
                    ('left', '>=', self.left),
                    ('right', '<=', self.right),
                    ('is_distributor', '=', True),
                    ])]

    @classmethod
    def _export_skips(cls):
        result = super(DistributionNetwork, cls)._export_skips()
        result.add('commercial_products')
        return result

    @classmethod
    def get_all_distributors(cls):
        res = cls._get_all_distributors_cache.get('all_distributors', None)
        if res is None:
            res = [x.id for x in cls.search([('is_distributor', '=', True)])]
            cls._get_all_distributors_cache.set('all_distributors', res)
        return res


class CommercialProduct(model.CodedMixin, model.CoogView):
    'Commercial Product'

    __name__ = 'distribution.commercial_product'
    _func_key = 'code'

    product = fields.Many2One('offered.product', 'Technical Product', domain=[
            ('start_date', '<=', Eval('start_date')),
            If(Eval('context', {}).contains('company'),
                ('company', '=', Eval('context', {}).get('company')),
                ('id', '>', 0))],
        depends=['start_date'], required=True, ondelete='RESTRICT',
        select=True)
    dist_networks = fields.Many2Many('distribution.network-commercial_product',
        'com_product', 'dist_network', 'Distribution Networks')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    description = fields.Text('Description', translate=True)

    @classmethod
    def copy(cls, products, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('dist_networks', None)
        return super(CommercialProduct, cls).copy(products, default=default)

    @staticmethod
    def default_start_date():
        return utils.today()

    @classmethod
    def _export_light(cls):
        return super(CommercialProduct, cls)._export_light() | \
            {'dist_networks', 'product'}


class DistributionNetworkComProductRelation(model.CoogSQL):
    'Relation Distribution Network - Commercial Product'

    __name__ = 'distribution.network-commercial_product'

    dist_network = fields.Many2One('distribution.network',
        'Distribution Network', ondelete='CASCADE')
    com_product = fields.Many2One('distribution.commercial_product',
        'Commercial Product', ondelete='RESTRICT')
