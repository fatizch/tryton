from trytond.model import fields

from trytond.modules.insurance_collective import GroupRoot
from trytond.modules.insurance_contract_subscription import \
    ContractSubscription

__all__ = [
    'GroupContractSubscription',
]


class GroupContractSubscription(GroupRoot, ContractSubscription):
    'Contract'

    __name__ = 'ins_collective.contract'

    is_custom = fields.Function(
        fields.Boolean('Custom'),
        'get_is_custom', 'set_is_custom')

    def get_is_custom(self, name):
        return False

    @classmethod
    def set_is_custom(cls, contracts, name, vals):
        pass
