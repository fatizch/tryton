from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields
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
        cls.kind.selection.append(('subscription', 'Contract Subscription'))


class ContractSubscribeFindProcess(ProcessStart):
    'ContractSubscribe Find Process'

    __name__ = 'contract.subscribe.find_process'

    com_product = fields.Many2One('distribution.commercial_product',
        'Commercial Product', domain=[
            ('id', 'in', Eval('possible_com_product')),
            ['OR',
                [('end_date', '>=', Eval('date'))],
                [('end_date', '=', None)],
                ],
            ['OR',
                [('start_date', '<=', Eval('date'))],
                [('start_date', '=', None)],
                ],
            ], depends=['possible_com_product', 'date'])
    dist_network = fields.Many2One('distribution.network',
        'Distribution Network')
    product = fields.Many2One('offered.product', 'Product')
    possible_com_product = fields.Function(
        fields.Many2Many('distribution.commercial_product', None,
            None, 'Commercial Products Available'),
        'on_change_with_possible_com_product')

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
        result.append('com_product')
        return result

    @classmethod
    def default_dist_network(cls):
        User = Pool().get('res.user')
        user = User(Transaction().user)
        return user.dist_network.id if user.dist_network else None

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'contract')])[0].id

    def get_possible_com_product(self):
        return self.dist_network.all_com_products if self.dist_network else []

    @fields.depends('dist_network')
    def on_change_with_possible_com_product(self, name=None):
        return [x.id for x in self.get_possible_com_product()]

    @fields.depends('com_product', 'product')
    def on_change_with_product(self):
        if not self.com_product:
            return None
        return self.com_product.product.id


class ContractSubscribe(ProcessFinder):
    'Contract Subscribe'

    __name__ = 'contract.subscribe'

    @classmethod
    def get_parameters_model(cls):
        return 'contract.subscribe.find_process'

    @classmethod
    def get_parameters_view(cls):
        return \
            'contract_insurance_process.contract_subscribe_find_process_form'

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ContractSubscribe,
            self).init_main_object_from_process(obj, process_param)
        if res:
            res, err = obj.init_from_product(process_param.product,
                process_param.date)
            obj.dist_network = process_param.dist_network
            errs += err
        return res, errs
