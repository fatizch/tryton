# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'ContractSubscribeFindProcess',
    'ContractSubscribe',
    ]


class ContractSubscribeFindProcess:
    __name__ = 'contract.subscribe.find_process'

    distributor = fields.Many2One('distribution.network', 'Distributor',
        required=True, domain=[('is_distributor', '=', True)])
    authorized_commercial_products = fields.Many2Many(
        'distribution.commercial_product', None, None,
        'Authorized Commercial Products', states={'invisible': False})
    commercial_product = fields.Many2One('distribution.commercial_product',
        'Product', domain=[
            ('id', 'in', Eval('authorized_commercial_products'))],
        depends=['authorized_commercial_products'], required=True)

    @classmethod
    def __setup__(cls):
        super(ContractSubscribeFindProcess, cls).__setup__()
        cls.product.states['invisible'] = True

    @fields.depends('distributor', 'effective_date')
    def on_change_with_authorized_commercial_products(self):
        if self.distributor and self.effective_date is not None:
            return [x.id for x in self.distributor.all_com_products
                if (not x.start_date or
                    (x.start_date <= self.effective_date)) and
                (not x.end_date or (self.effective_date <= x.end_date))]
        else:
            return []

    @fields.depends('commercial_product')
    def on_change_with_product(self):
        if self.commercial_product is not None:
            return self.commercial_product.product.id

    @fields.depends('commercial_product')
    def on_change_with_good_process(self):
        if self.commercial_product is not None:
            self.product = self.commercial_product.product
        return super(ContractSubscribeFindProcess,
            self).on_change_with_good_process()


class ContractSubscribe:
    __name__ = 'contract.subscribe'

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ContractSubscribe,
            self).init_main_object_from_process(obj, process_param)
        if res:
            obj.dist_network = process_param.distributor
        return res, errs
