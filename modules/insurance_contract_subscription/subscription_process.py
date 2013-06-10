import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, fields
from trytond.modules.coop_process import ProcessFinder, ProcessParameters


__all__ = [
    'SubscriptionManager',
    'ProcessDesc',
    'SubscriptionProcessParameters',
    'SubscriptionProcessFinder',
]


class SubscriptionManager(model.CoopSQL):
    'Subscription Manager'
    '''Temporary object used during the subscription, it is dropped as soon
    as the contract is activated'''

    __name__ = 'ins_contract.subscription_mgr'

    contract = fields.Reference(
        'Contract',
        [
            ('contract.contract', 'Contract'),
            ('ins_collective.contract', 'Contract')],
    )
    is_custom = fields.Boolean('Custom')


class ProcessDesc():
    'Process Desc'

    __metaclass__ = PoolMeta

    __name__ = 'process.process_desc'

    @classmethod
    def __setup__(cls):
        super(ProcessDesc, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('subscription', 'Contract Subscription'))


class SubscriptionProcessParameters(ProcessParameters):
    'Subscription Process Parameters'

    __name__ = 'ins_contract.subscription_process_parameters'

    dist_network = fields.Many2One('distribution.dist_network',
        'Distribution Network', on_change=['dist_network', 'possible_brokers',
        'broker'])
    possible_brokers = fields.Function(
        fields.Many2Many('party.party', None, None, 'Possible Brokers',
            on_change_with=['dist_network', 'possible_brokers'],
            states={'invisible': True},
            ), 'on_change_with_possible_brokers')
    broker = fields.Many2One('party.party', 'Broker',
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
        'Product Commercial',
        domain=[
                ('id', 'in', Eval('possible_com_product')),
                ['OR',
                    [('end_date', '>=', Eval('date'))],
                    [('end_date', '=', None)],
                ],
                ['OR',
                    [('start_date', '<=', Eval('date'))],
                    [('start_date', '=', None)],
                ],
            ],
        depends=['possible_com_product', 'date'],
        on_change=['com_product', 'product'])
    product = fields.Many2One('offered.product', 'Product',
        states={'invisible': True})

    @classmethod
    def build_process_domain(cls):
        result = super(
            SubscriptionProcessParameters, cls).build_process_domain()
        result.append(('for_products', '=', Eval('product')))
        result.append(('kind', '=', 'subscription'))
        return result

    @classmethod
    def build_process_depends(cls):
        result = super(
            SubscriptionProcessParameters, cls).build_process_depends()
        result.append('product')
        return result

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'contract.contract')])[0].id

    @classmethod
    def default_dist_network(cls):
        User = Pool().get('res.user')
        user = User(Transaction().user)
        return user.dist_network.id if user.dist_network else None

    def get_possible_com_product(self):
        return (self.dist_network.get_commercial_products()
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
        if self.broker and self.broker.id not in res['possible_brokers']:
            res['broker'] = None
        elif len(res['possible_brokers']) == 1:
            res['broker'] = res['possible_brokers'][0]
        return res


class SubscriptionProcessFinder(ProcessFinder):
    'Subscription Process Finder'

    __name__ = 'ins_contract.subscription_process_finder'

    @classmethod
    def get_parameters_model(cls):
        return 'ins_contract.subscription_process_parameters'

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'insurance_contract_subscription',
            'subscription_process_parameters_form')

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(SubscriptionProcessFinder,
            self).init_main_object_from_process(obj, process_param)
        if res:
            res, err = obj.init_from_offered(process_param.product,
                process_param.date)
            obj.get_or_create_management_role('commission',
                process_param.broker)
            obj.dist_network = process_param.dist_network
            errs += err
        return res, errs
