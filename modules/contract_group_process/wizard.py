from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

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
        super(ContractSubscribeFindProcess, cls).__setup__()
        cls.lines.product = ['AND', cls.lines.product,
            [('is_group', '=', Eval('is_group'))]]
        cls.product.depends += ['is_group']


class ContractSubscribe:
    __name__ = 'contract.subscribe'

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'contract_group_process',
            'contract_subscribe_find_process_form')
