import copy

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import fields, utils

__all__ = [
    'GroupSubscriptionProcessParameters',
    'SubscriptionProcessFinder',
    ]


class GroupSubscriptionProcessParameters():
    'Group Process Parameters'

    __name__ = 'ins_contract.subscription_process_parameters'
    __metaclass__ = PoolMeta

    is_group = fields.Boolean('Group', on_change=['product', 'is_group',
        'possible_com_product', 'dist_network', 'com_product'])

    @classmethod
    def __setup__(cls):
        utils.update_domain(cls, 'product',
            [('is_group', '=', Eval('is_group'))])
        utils.update_depends(cls, 'product', ['is_group'])
        cls.possible_com_product = copy.copy(cls.possible_com_product)
        cls.possible_com_product.on_change_with.append('is_group')
        super(GroupSubscriptionProcessParameters, cls).__setup__()

    def on_change_is_group(self):
        res = {}
        com_products = self.get_possible_com_product()
        res['possible_com_product'] = [x.id for x in com_products]
        if self.com_product and not self.com_product in com_products:
            res['com_product'] = None
        if (self.product and self.product not in
                [x.product for x in com_products]):
            res['product'] = None
        return res

    def get_possible_com_product(self):
        res = super(GroupSubscriptionProcessParameters,
            self).get_possible_com_product()
        if not res:
            return res
        return [x for x in res[0].browse([y.id for y in res])
            if x.product.is_group == self.is_group]


class SubscriptionProcessFinder():
    'Subscription Process Finder'

    __name__ = 'ins_contract.subscription_process_finder'
    __metaclass__ = PoolMeta

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(SubscriptionProcessFinder,
            self).init_main_object_from_process(obj, process_param)
        if res:
            res, err = obj.init_from_offered(process_param.product,
                process_param.date)
            errs += err
        return res, errs

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'insurance_collective_subscription',
            'subscription_process_parameters_form')
