import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, utils
from trytond.modules.process_cog import ProcessFinder, ProcessStart


__metaclass__ = PoolMeta
__all__ = [
    'Process',
    'ContractSubscribeFindProcess',
    'ContractSubscribe',
    ]


class Process:
    __name__ = 'process'

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('subscription', 'Contract Subscription'))


class ContractSubscribeFindProcess(ProcessStart):
    'ContractSubscribe Find Process'

    __name__ = 'contract.subscribe.find_process'

    dist_network = fields.Many2One('distribution.network',
        'Distribution Network', on_change=['dist_network', 'possible_brokers',
            'business_provider', 'management_delegation'])
    possible_brokers = fields.Function(
        fields.Many2Many('party.party', None, None, 'Possible Brokers',
            on_change_with=['dist_network', 'possible_brokers'],
            states={'invisible': True},
            ), 'on_change_with_possible_brokers')
    business_provider = fields.Many2One('party.party', 'Business Provider',
        domain=[
            ('id', 'in', Eval('possible_brokers')),
            ('is_broker', '=', True),
            ], depends=['possible_brokers'])
    delegated_manager = fields.Many2One('party.party', 'Delegated Manager',
        domain=[
            ('id', 'in', Eval('possible_brokers')),
            ('is_broker', '=', True),
            ], depends=['possible_brokers'])
    possible_com_product = fields.Function(
        fields.Many2Many('distribution.commercial_product', None,
            None, 'Commercial Products Available',
            on_change_with=['dist_network'],
            states={'invisible': True}),
        'on_change_with_possible_com_product')
    com_product = fields.Many2One('distribution.commercial_product',
        'Product Commercial', domain=[
            ('id', 'in', Eval('possible_com_product')),
            ['OR',
                [('end_date', '>=', Eval('date'))],
                [('end_date', '=', None)],
                ],
            ['OR',
                [('start_date', '<=', Eval('date'))],
                [('start_date', '=', None)],
                ],
            ], depends=['possible_com_product', 'date'],
        on_change=['com_product', 'product'])
    product = fields.Many2One('offered.product', 'Product',
        states={'invisible': True})

    @classmethod
    def build_process_domain(cls):
        result = super(
            ContractSubscribeFindProcess, cls).build_process_domain()
        result.append(('for_products', '=', Eval('product')))
        result.append(('kind', '=', 'subscription'))
        return result

    @classmethod
    def build_process_depends(cls):
        result = super(
            ContractSubscribeFindProcess, cls).build_process_depends()
        result.append('product')
        return result

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'contract')])[0].id

    @classmethod
    def default_dist_network(cls):
        User = Pool().get('res.user')
        user = User(Transaction().user)
        return user.dist_network.id if user.dist_network else None

    def get_possible_com_product(self):
        return (self.dist_network.all_com_products
            if self.dist_network else [])

    def on_change_with_possible_com_product(self, name=None):
        return [x.id for x in self.get_possible_com_product()]

    def on_change_com_product(self):
        res = {}
        if (not self.com_product
                or self.product and self.com_product.product != self.product):
            res = {'product': None}
        else:
            res = {'product': self.com_product.product.id}
        return res

    def on_change_with_possible_brokers(self, name=None):
        if self.dist_network:
            return [x.id for x in self.dist_network.get_brokers()]
        else:
            return []

    def on_change_dist_network(self):
        res = {}
        res['possible_brokers'] = self.on_change_with_possible_brokers()
        if (not utils.is_none(self, 'business_provider')
                and self.business_provider.id not in res['possible_brokers']):
            res['business_provider'] = None
        elif (not utils.is_none(self, 'delegated_manager')
                and self.delegated_manager.id not in res['possible_brokers']):
            res['delegated_manager'] = None
        elif len(res['possible_brokers']) == 1:
            res['business_provider'] = res['possible_brokers'][0]
            res['delegated_manager'] = res['possible_brokers'][0]
        return res


class ContractSubscribe(ProcessFinder):
    'Contract Subscribe'

    __name__ = 'contract.subscribe'

    @classmethod
    def get_parameters_model(cls):
        return 'contract.subscribe.find_process'

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'contract_insurance_process',
            'contract_subscribe_find_process_form')

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ContractSubscribe,
            self).init_main_object_from_process(obj, process_param)
        if res:
            res, err = obj.init_from_offered(process_param.product,
                process_param.date)
            if process_param.business_provider:
                obj.get_or_create_agreement('business_provider',
                    process_param.business_provider)
            if process_param.delegated_manager:
                obj.get_or_create_agreement('management',
                    process_param.delegated_manager)
            obj.dist_network = process_param.dist_network
            errs += err
        return res, errs
