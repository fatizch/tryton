from trytond.model import fields
from trytond.pool import PoolMeta

from trytond.modules.insurance_collective.collective_contract import \
    CONTRACT_KIND

__all__ = [
    'GroupSubscriptionProcessParameters',
    'SubscriptionProcessFinder',
]


class GroupSubscriptionProcessParameters():
    'Group Process Parameters'

    __name__ = 'ins_contract.subscription_process_parameters'
    __metaclass__ = PoolMeta

    kind = fields.Selection(CONTRACT_KIND, 'Kind')

    @staticmethod
    def default_kind():
        return 'individual'


class SubscriptionProcessFinder():
    'Subscription Process Finder'

    __name__ = 'ins_contract.subscription_process_finder'
    __metaclass__ = PoolMeta

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(SubscriptionProcessFinder,
            self).init_main_object_from_process(obj, process_param)
        if res:
            res, err = obj.init_from_offered(process_param.product,
                process_param.date, kind=process_param.kind)
            errs += err
        return res, errs

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'insurance_collective_subscription',
            'subscription_process_parameters_form')
