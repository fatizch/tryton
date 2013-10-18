from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.rpc import RPC

from trytond.modules.coop_utils import utils, fields, coop_string

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'LifeOption',
    'LifeCoveredData',
    'PriceLine',
    ]


class Contract():
    'Contract'

    __name__ = 'contract.contract'

    def check_covered_amounts(self, at_date=None):
        if not at_date:
            at_date = self.start_date
        options = dict([
            (option.offered.code, option) for option in self.options])
        res, errs = (True, [])
        for covered_element in self.covered_elements:
            for covered_data in covered_element.covered_data:
                if (covered_data.start_date > at_date
                        or hasattr(covered_data, 'end_date') and
                        covered_data.end_date and
                        covered_data.end_date > at_date):
                    continue
                coverage = covered_data.option.offered
                validity, errors = coverage.get_result(
                    'coverage_amount_validity',
                    {
                        'date': at_date,
                        'sub_elem': covered_element,
                        'data': covered_data,
                        'option': options[coverage.code],
                        'contract': self,
                        'appliable_conditions_date':
                        self.appliable_conditions_date,
                    })
                res = res and (not validity or validity[0])
                if validity:
                    errs += validity[1]
                errs += errors
        return (res, errs)

    @classmethod
    def get_possible_contracts_from_party(cls, party, at_date):
        res = super(Contract, cls).get_possible_contracts_from_party(party,
            at_date)
        if not party:
            return res
        for cov_elem in cls.get_possible_covered_elements(party, at_date):
            contract = cov_elem.main_contract
            #TODO : Temporary Hack Date validation should be done with domain
            #and in get_possible_covered_elements
            if contract and contract.is_active_at_date(at_date):
                res.append(contract)
        return res

    @classmethod
    def get_possible_covered_elements(cls, party, at_date):
        CoveredElement = Pool().get('ins_contract.covered_element')
        return CoveredElement.get_possible_covered_elements(party, at_date)


class LifeOption():
    'Subscribed Life Coverage'

    __name__ = 'contract.subscribed_option'

    def get_covered_data(self, covered_person):
        for covered_data in self.covered_data:
            if not hasattr(covered_data.covered_element, 'person'):
                continue
            if covered_data.covered_element.party == covered_person:
                return covered_data

    def get_coverage_amount(self, covered_person):
        covered_data = self.get_covered_data(covered_person)
        if covered_data:
            return covered_data.coverage_amount
        return 0


class PriceLine():
    'Price Line'

    __name__ = 'ins_contract.price_line'

    @classmethod
    def get_line_target_models(cls):
        res = super(PriceLine, cls).get_line_target_models()
        res.append(('life_contract.covered_data',
            'life_contract.covered_data'))
        return res


class LifeCoveredData():
    'Covered Data'

    __name__ = 'ins_contract.covered_data'

    coverage_amount = fields.Numeric('Coverage Amount', states={
            'invisible': ~Eval('with_coverage_amount'),
            # 'required': ~~Eval('with_coverage_amount'),
            }, depends=['with_coverage_amount', 'currency'])
    with_coverage_amount = fields.Function(
        fields.Boolean('With Coverage Amount', states={'invisible': True}),
        'get_with_coverage_amount')

    @classmethod
    def __setup__(cls):
        super(LifeCoveredData, cls).__setup__()
        cls.__rpc__.update({'get_possible_amounts': RPC(instantiate=0)})

    def get_possible_amounts(self):
        if utils.is_none(self, 'option'):
            return [('', '')]
        the_coverage = self.get_coverage()
        vals = the_coverage.get_result(
            'allowed_amounts',
            {
                'date': self.start_date,
                'appliable_conditions_date':
                self.option.contract.appliable_conditions_date,
                #'contract': abstract.WithAbstract.get_abstract_objects(
                #    wizard, 'for_contract')
            },)[0]
        if vals:
            res = map(lambda x: (x, x),
                map(lambda x: coop_string.amount_as_string(x, self.currency),
                    vals))
            return [('', '')] + res
        return [('', '')]

    def get_with_coverage_amount(self, name):
        return len(self.get_possible_amounts()) > 1

    def is_party_covered(self, party, at_date):
        return self.covered_element.is_party_covered(party, at_date,
            self.option)

    @classmethod
    def default_coverage_amount(cls):
        return None
