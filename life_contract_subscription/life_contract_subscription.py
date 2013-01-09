import copy

from decimal import Decimal

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.rpc import RPC

from trytond.modules.insurance_contract_subscription import CoveredData
from trytond.modules.insurance_contract_subscription import CoveredElement

__all__ = [
    'CoveredPersonSubs',
    'CoveredDataSubs',
]


class CoveredPersonSubs(CoveredElement):
    'Covered Person'

    __metaclass__ = PoolMeta

    __name__ = 'life_contract.covered_person'


class CoveredDataSubs(CoveredData):
    'Covered Data'

    __metaclass__ = PoolMeta

    __name__ = 'life_contract.covered_data'

    coverage_amount_selection = fields.Function(
        fields.Selection(
            'get_allowed_amounts',
            'Coverage Amount',
            selection_parameters=['for_coverage', 'start_date'],
            depends=['for_coverage', 'start_date', 'coverage_amount'],
            sort=False,
            on_change=['coverage_amount', 'coverage_amount_selection'],
        ),
        'get_coverage_amount_selection',
        'setter_void',
    )

    @classmethod
    def __setup__(cls):
        super(CoveredDataSubs, cls).__setup__()
        cls.for_covered = copy.copy(cls.for_covered)
        cls.for_covered.model_name = 'life_contract.covered_person'
        cls.__rpc__.update({
            'get_allowed_amounts': RPC(instantiate=0),
        })
        cls._error_messages.update({
            'coverage_amount_needed': 'A coverage amount must be provided :'})

    def get_allowed_amounts(self):
        if not (hasattr(self, 'for_coverage') and self.for_coverage):
            return []
        the_coverage = self.for_coverage
        vals = the_coverage.get_result(
            'allowed_amounts',
            {
                'date': self.start_date,
                #'contract': utils.WithAbstract.get_abstract_objects(
                #    wizard, 'for_contract')
            },)[0]
        if vals:
            return map(lambda x: (x, x), map(lambda x: '%.2f' % x, vals))
        return ''

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

