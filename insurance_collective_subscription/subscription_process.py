from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.modules.coop_utils import model, utils
from trytond.modules.insurance_collective import GroupRoot
from trytond.modules.insurance_contract_subscription import \
    ContractSubscription, SubscriptionManager

__all__ = [
    'GroupContractSubscription',
    'GroupSubscriptionManager',
]


class GroupContractSubscription(GroupRoot, ContractSubscription):
    'Contract'

    __name__ = 'ins_collective.contract'

    is_custom = fields.Function(
        fields.Boolean('Custom'),
        'get_is_custom', 'set_is_custom')

    @classmethod
    def __setup__(cls):
        super(GroupContractSubscription, cls).__setup__()

    def get_is_custom(self, name):
        if not (hasattr(self, 'subscription_mgr') and self.subscription_mgr):
            return False
        return self.subscription_mgr[0].is_custom

    @classmethod
    def set_is_custom(cls, contracts, name, vals):
        Model = utils.get_relation_model(cls, 'subscription_mgr')
        for contract in contracts:
            if not contract.subscription_mgr:
                Model.create(
                    [
                        {
                            'contract': 'ins_collective.contract,%s' % contract.id,
                            'is_custom': vals,
                        }
                    ])
            else:
                Model.write([contract.subscription_mgr[0]],
                    {'is_custom': vals})

    def clone_offered(self):
        template = self.offered
        self.offered = utils.instanciate_relation(self.__class__, 'offered')
        self.offered.template = template
        with Transaction().set_context(subscriber=self.subscriber.id):
            offered_dict = self.offered.on_change_template()
        for key, val in offered_dict.iteritems():
            if type(val) != dict:
                setattr(self.offered, key, val)
        return True, ()


class GroupSubscriptionManager(GroupRoot, SubscriptionManager):
    'Subscription Manager'

    __name__ = 'ins_collective.subscription_mgr'

    is_custom = fields.Boolean('Custom')

#    @classmethod
#    def __setup__(cls):
#        print '%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%'
#        print super(GroupSubscriptionManager, cls).__name__
#        super(GroupSubscriptionManager, cls).__setup__()

    @classmethod
    def get_convert_dict(cls):
        res = super(GroupSubscriptionManager, cls).get_convert_dict()
        res['ins_contract.subscription_mgr'] = (
            'ins_collective.subscription_mgr')
        return res
