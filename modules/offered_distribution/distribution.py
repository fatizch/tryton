# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields, utils, coop_string

__metaclass__ = PoolMeta
__all__ = [
    'DistributionNetwork',
    'CommercialProduct',
    'DistributionNetworkComProductRelation',
    ]


class DistributionNetwork:
    __name__ = 'distribution.network'

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
    company = fields.Many2One('company.company', 'Company',
        ondelete='RESTRICT', depends=['commercial_products'])

    def get_parent_com_products_id(self, name):
        ComProduct = Pool().get('distribution.commercial_product')
        return [x.id for x in ComProduct.search([
                    ('dist_networks.left', '<', self.left),
                    ('dist_networks.right', '>', self.right),
                    ])]

    def get_all_commercial_products_id(self, name):
        return [x.id for x in set(
                self.commercial_products + self.parent_com_products)]

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None

    @classmethod
    def _export_skips(cls):
        result = super(DistributionNetwork, cls)._export_skips()
        result.add('commercial_products')
        return result


class CommercialProduct(model.CoopSQL, model.CoopView):
    'Commercial Product'

    __name__ = 'distribution.commercial_product'

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
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
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

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    @classmethod
    def _export_light(cls):
        return super(CommercialProduct, cls)._export_light() | \
            {'dist_networks', 'product'}


class DistributionNetworkComProductRelation(model.CoopSQL):
    'Relation Distribution Network - Commercial Product'

    __name__ = 'distribution.network-commercial_product'

    dist_network = fields.Many2One('distribution.network',
        'Distribution Network', ondelete='CASCADE')
    com_product = fields.Many2One('distribution.commercial_product',
        'Commercial Product', ondelete='RESTRICT')
