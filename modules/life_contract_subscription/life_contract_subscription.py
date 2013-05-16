from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.pyson import Eval

from trytond.modules.coop_utils import fields, utils, coop_string


__all__ = [
    'LifeContractSubscription',
    'CoveredPersonSubs',
    'CoveredDataSubs',
]


class LifeContractSubscription():
    'Life Contract'

    __name__ = 'ins_contract.contract'
    __metaclass__ = PoolMeta

    def set_subscriber_as_covered_element(self):
        CoveredElement = Pool().get('ins_contract.covered_element')
        subscriber = self.get_policy_owner(self.start_date)
        if not utils.is_none(self, 'covered_elements'):
            for covered_element in self.covered_elements:
                if covered_element.party == subscriber:
                    return True
        covered_element = CoveredElement()
        covered_element.party = subscriber
        item_descs = CoveredElement.get_possible_item_desc(self)
        if len(item_descs) == 1:
            covered_element.item_desc = item_descs[0]
        if not hasattr(self, 'covered_elements'):
            self.covered_elements = [covered_element]
        else:
            self.covered_elements = list(self.covered_elements)
            self.covered_elements.append(covered_element)
        return True


class CoveredPersonSubs():
    'Covered Person'

    __name__ = 'ins_contract.covered_element'
    __metaclass__ = PoolMeta


class CoveredDataSubs():
    'Covered Data'

    __name__ = 'ins_contract.covered_data'
    __metaclass__ = PoolMeta

    coverage_amount_selection = fields.Function(
        fields.Selection(
            'get_possible_amounts',
            'Coverage Amount',
            selection_change_with=['option', 'start_date',
                'covered_element', 'currency'],
            depends=['option', 'start_date', 'coverage_amount',
                'with_coverage_amount'],
            sort=False,
            on_change=['coverage_amount', 'coverage_amount_selection',
                'currency'],
            states={
                'invisible': ~Eval('with_coverage_amount'),
                # 'required': ~~Eval('with_coverage_amount'),
                }
        ),
        'get_coverage_amount_selection',
        'setter_void',
    )

    @classmethod
    def __setup__(cls):
        super(CoveredDataSubs, cls).__setup__()
        cls._error_messages.update({
            'coverage_amount_needed': 'A coverage amount must be provided :'})

    def get_coverage_amount_selection(self, name):
        if (hasattr(self, 'coverage_amount') and self.coverage_amount):
            # return '%.2f' % self.coverage_amount
            return coop_string.amount_as_string(self.coverage_amount,
                self.currency)
        return ''

    def on_change_coverage_amount_selection(self):
        if not utils.is_none(self, 'coverage_amount_selection'):
            return {'coverage_amount': coop_string.get_amount_from_currency(
                    self.coverage_amount_selection, self.currency)}
        else:
            return {'coverage_amount': None}

    @classmethod
    def setter_void(cls, covered_datas, name, values):
        pass
