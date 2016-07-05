# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'CoveredElement',
    'Beneficiary',
    ]


class Contract:
    __name__ = 'contract'

    dist_network = fields.Many2One('distribution.network',
        'Distribution Network', domain=[('company', '=', Eval('company'))],
        states={'readonly': Eval('status') != 'quote'},
        depends=['company', 'status'], ondelete='RESTRICT')
    com_product = fields.Function(
        fields.Many2One('distribution.commercial_product',
            'Commercial Product'),
        'get_com_product_id')
    allowed_portfolios = fields.Function(
        fields.Many2Many('distribution.network', None, None,
            'Allowed Portfolios'),
        'on_change_with_allowed_portfolios')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.subscriber.depends.append('allowed_portfolios')
        cls.subscriber.domain = [cls.subscriber.domain, ['OR',
                ('portfolio', 'in', Eval('allowed_portfolios')),
                ('portfolio', '=', None)]]

    def get_com_product_id(self, name):
        if not self.dist_network:
            return None
        com_products = utils.get_good_versions_at_date(self.dist_network,
            'all_com_products', self.start_date)
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

    @fields.depends('dist_network')
    def on_change_with_allowed_portfolios(self, name):
        if not self.dist_network:
            return []
        return [x.id for x in self.dist_network.visible_portfolios]

    @classmethod
    def _export_light(cls):
        return super(Contract, cls)._export_light() | set(['dist_network'])


class CoveredElement:
    __name__ = 'contract.covered_element'

    allowed_portfolios = fields.Function(
        fields.Many2Many('distribution.network', None, None,
        'Allowed Portfolios'),
        'get_allowed_portfolios')

    @classmethod
    def __setup__(cls):
        super(CoveredElement, cls).__setup__()
        cls.party.depends.append('allowed_portfolios')
        cls.party.domain = [cls.party.domain, ['OR',
                ('portfolio', 'in', Eval('allowed_portfolios')),
                ('portfolio', '=', None)]]

    def get_allowed_portfolios(self, name=None):
        if not self.main_contract or not self.main_contract.dist_network:
            return []
        else:
            return [x.id for x in
                self.main_contract.dist_network.visible_portfolios]

    @fields.depends('allowed_portfolios')
    def on_change_contract(self):
        super(CoveredElement, self).on_change_contract()
        self.allowed_portfolios = self.get_allowed_portfolios()

    @fields.depends('allowed_portfolios')
    def on_change_parent(self):
        super(CoveredElement, self).on_change_parent()
        self.allowed_portfolios = self.get_allowed_portfolios()


class Beneficiary:
    __name__ = 'contract.option.beneficiary'

    allowed_portfolios = fields.Function(
        fields.Many2Many('distribution.network', None, None,
        'Allowed Portfolios'),
        'get_allowed_portfolios')

    @classmethod
    def __setup__(cls):
        super(Beneficiary, cls).__setup__()
        cls.party.depends.append('allowed_portfolios')
        cls.party.domain = [cls.party.domain, ['OR',
                ('portfolio', 'in', Eval('allowed_portfolios')),
                ('portfolio', '=', None)]]

    @classmethod
    def view_attributes(cls):
        return super(Beneficiary, cls).view_attributes() + [(
                '/form/group[@id="invisible"]', 'invisible', True)]

    @fields.depends('option')
    def get_allowed_portfolios(self, name=None):
        if not self.option.covered_element.contract.dist_network:
            return []
        return [x.id for x in
            self.option.covered_element.contract.dist_network.
            visible_portfolios]

    @fields.depends('allowed_portfolios', 'option')
    def on_change_option(self):
        self.allowed_portfolios = self.get_allowed_portfolios()
