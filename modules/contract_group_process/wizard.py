from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'ContractSubscribeFindProcess',
    'ContractSubscribe',
    ]


class ContractSubscribeFindProcess:
    __name__ = 'contract.subscribe.find_process'

    is_group = fields.Boolean('Group')

    @classmethod
    def __setup__(cls):
        utils.update_domain(cls, 'product',
            [('is_group', '=', Eval('is_group'))])
        utils.update_depends(cls, 'product', ['is_group'])
        cls.possible_com_product.on_change_with.add('is_group')
        super(ContractSubscribeFindProcess, cls).__setup__()

    @fields.depends('product', 'is_group', 'possible_com_product',
        'dist_network', 'com_product')
    def on_change_is_group(self):
        com_products = self.get_possible_com_product()
        self.possible_com_product = [x for x in com_products]
        if self.com_product and self.com_product not in com_products:
            self.com_product = None
        if (self.product and self.product not in
                [x.product for x in com_products]):
            self.product = None

    def get_possible_com_product(self):
        res = super(ContractSubscribeFindProcess,
            self).get_possible_com_product()
        if not res:
            return res
        return [x for x in res[0].browse([y.id for y in res])
            if x.product.is_group == self.is_group]


class ContractSubscribe:
    __name__ = 'contract.subscribe'

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ContractSubscribe,
            self).init_main_object_from_process(obj, process_param)
        if res:
            res, err = obj.init_from_offered(process_param.product,
                process_param.date)
            errs += err
        return res, errs

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'contract_group_process',
            'contract_subscribe_find_process_form')
