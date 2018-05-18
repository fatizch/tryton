# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils

__all__ = [
    'Contract',

    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    dist_network = fields.Many2One('distribution.network',
        'Distribution Network', domain=[('company', '=', Eval('company'))],
        states={'readonly': Eval('status') != 'quote'},
        depends=['company', 'status'], ondelete='RESTRICT')
    com_product = fields.Function(
        fields.Many2One('distribution.commercial_product',
            'Commercial Product'),
        'get_com_product_id')

    def get_com_product_id(self, name):
        if not self.dist_network:
            return None
        com_products = utils.get_good_versions_at_date(self.dist_network,
            'all_com_products', self.appliable_conditions_date)
        com_product = [x for x in com_products if x.product == self.product]
        if com_product:
            return com_product[0].id

    def get_dist_network(self):
        return self.dist_network

    def init_contract(self, product, party, contract_dict=None):
        super(Contract, self).init_contract(product, party, contract_dict)
        if not contract_dict or 'dist_network' not in contract_dict:
            return
        DistributionNetwork = Pool().get('distribution.network')
        self.dist_network, = DistributionNetwork.search(
            [('code', '=', contract_dict['dist_network']['code'])], limit=1,
            order=[])

    @classmethod
    def _export_light(cls):
        return super(Contract, cls)._export_light() | set(['dist_network'])

    @classmethod
    def search(cls, domain, *args, **kwargs):
        dist_network = Pool().get('res.user')(Transaction().user).dist_network
        if dist_network:
            domain = ['AND', domain,
                [('dist_network', 'in',
                    [x.id for x in dist_network.all_children])]]
        return super(Contract, cls).search(domain, *args, **kwargs)
