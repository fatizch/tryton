from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.rpc import RPC

from trytond.modules.coop_utils import fields


__all__ = [
    'CoveredPersonSubs',
    'CoveredDataSubs',
]


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
            'get_allowed_amounts',
            'Coverage Amount',
            selection_change_with=['coverage', 'start_date'],
            depends=['coverage', 'start_date', 'coverage_amount'],
            sort=False,
            on_change=['coverage_amount', 'coverage_amount_selection'],
        ),
        'get_coverage_amount_selection',
        'setter_void',
    )

    @classmethod
    def __setup__(cls):
        super(CoveredDataSubs, cls).__setup__()
#        cls.covered_element = copy.copy(cls.covered_element)
#        cls.covered_element.model_name = 'life_contract.covered_person'
        cls.__rpc__.update({
            'get_allowed_amounts': RPC(instantiate=0),
        })
        cls._error_messages.update({
            'coverage_amount_needed': 'A coverage amount must be provided :'})

    def get_allowed_amounts(self):
        if not (hasattr(self, 'coverage') and self.coverage):
            return [('', '')]
        the_coverage = self.coverage
        vals = the_coverage.get_result(
            'allowed_amounts',
            {
                'date': self.start_date,
                #'contract': abstract.WithAbstract.get_abstract_objects(
                #    wizard, 'for_contract')
            },)[0]
        if vals:
            res = map(lambda x: (x, x), map(lambda x: '%.2f' % x, vals))
            return [('', '')] + res
        return [('', '')]

    def get_coverage_amount_selection(self, name):
        if (hasattr(self, 'coverage_amount') and self.coverage_amount):
            return '%.2f' % self.coverage_amount
        return ''

    def on_change_coverage_amount_selection(self):
        if hasattr(self, 'coverage_amount_selection') and \
                self.coverage_amount_selection:
            return {'coverage_amount': Decimal(self.coverage_amount_selection)}
        else:
            return {'coverage_amount': None}

    @classmethod
    def setter_void(cls, covered_datas, name, values):
        pass
