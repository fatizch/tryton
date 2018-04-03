# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields


__all__ = [
    'ContractSubscribeFindProcess',
    'ContractSubscribe',
    ]


class ContractSubscribeFindProcess:
    __metaclass__ = PoolMeta
    __name__ = 'contract.subscribe.find_process'

    authorized_distributors = fields.Many2Many(
        'distribution.network', None, None, 'Authorized distributors',
        states={'invisible': True})
    distributor = fields.Many2One(
        'distribution.network', 'Distributor', required=True,
        domain=[('id', 'in', Eval('authorized_distributors'))],
        depends=['authorized_distributors'])
    authorized_commercial_products = fields.Many2Many(
        'distribution.commercial_product', None, None,
        'Authorized Commercial Products', states={'invisible': False})
    commercial_product = fields.Many2One(
        'distribution.commercial_product', 'Product', required=True,
        domain=[('id', 'in', Eval('authorized_commercial_products'))],
        depends=['authorized_commercial_products'])

    @classmethod
    def __setup__(cls):
        super(ContractSubscribeFindProcess, cls).__setup__()
        cls.product.states['invisible'] = True

    @staticmethod
    def default_distributor():
        candidates = [x.id for x in
            Pool().get('res.user')(Transaction().user).network_distributors]
        return candidates[0] if len(candidates) == 1 else None

    @fields.depends('distributor', 'appliable_conditions_date',
        'signature_date', 'start_date')
    def on_change_with_authorized_commercial_products(self):
        if self.distributor and self.appliable_conditions_date is not None:
            return [x.id for x in self.distributor.all_com_products
                if (not x.start_date or
                    (x.start_date <= self.appliable_conditions_date)) and
                (not x.end_date or (
                        self.appliable_conditions_date <= x.end_date))]
        else:
            return []

    @fields.depends('commercial_product', methods=['product'])
    def on_change_commercial_product(self):
        if self.commercial_product is not None:
            self.product = self.commercial_product.product.id
            res = self.simulate_init()
            if res and res.errors:
                self.unset_product()
        else:
            self.start_date_readonly = False
            self.product = None

    @fields.depends('commercial_product')
    def on_change_with_good_process(self):
        if self.commercial_product is not None:
            self.product = self.commercial_product.product
        return super(ContractSubscribeFindProcess,
            self).on_change_with_good_process()

    def unset_product(self):
        super(ContractSubscribeFindProcess, self).unset_product()
        self.commercial_product = None


class ContractSubscribe:
    __metaclass__ = PoolMeta
    __name__ = 'contract.subscribe'

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ContractSubscribe,
            self).init_main_object_from_process(obj, process_param)
        if res:
            obj.dist_network = process_param.distributor
        return res, errs

    def default_process_parameters(self, name):
        defaults = super(
            ContractSubscribe, self).default_process_parameters(name)
        candidates = [x.id for x in
            Pool().get('res.user')(Transaction().user).network_distributors]
        defaults.update({
            'authorized_distributors': candidates,
            })
        return defaults
