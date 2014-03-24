from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.rpc import RPC

from trytond.modules.cog_utils import utils, fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    'CoveredData',
    ]


class Contract:
    __name__ = 'contract'

    def update_coverage_amounts_if_needed(self, at_date=None):
        if not at_date:
            at_date = self.start_date
        for covered_element in self.covered_elements:
            values = {}
            to_update = {}
            for covered_data in covered_element.covered_data:
                values[covered_data.option.offered.id] = \
                    covered_data.coverage_amount
                rule_dict = {'date': at_date}
                covered_data.init_dict_for_rule_engine(rule_dict)
                result, errs = covered_data.option.offered.get_result(
                    'dependant_amount_coverage', rule_dict)
                if errs or result is None:
                    continue
                to_update[covered_data] = result.id
            for data, offered in to_update.iteritems():
                data.coverage_amount = values[offered]
                data.save()
        return True

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
                if not covered_data.with_coverage_amount:
                    continue
                coverage = covered_data.option.offered
                validity, errors = coverage.get_result(
                    'coverage_amount_validity', {
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
        CoveredElement = Pool().get('contract.covered_element')
        return CoveredElement.get_possible_covered_elements(party, at_date)


class ContractOption:
    __name__ = 'contract.option'

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


class CoveredData:
    __name__ = 'contract.covered_data'

    coverage_amount = fields.Numeric('Coverage Amount', states={
            'invisible': ~Eval('with_coverage_amount'),
            # 'required': ~~Eval('with_coverage_amount'),
            }, depends=['with_coverage_amount', 'currency'])
    with_coverage_amount = fields.Function(
        fields.Boolean('With Coverage Amount', states={'invisible': True}),
        'get_with_coverage_amount')

    @classmethod
    def __setup__(cls):
        super(CoveredData, cls).__setup__()
        cls.__rpc__.update({'get_possible_amounts': RPC(instantiate=0)})

    def get_possible_amounts(self):
        if utils.is_none(self, 'option'):
            return [('', '')]
        the_coverage = self.get_coverage()
        vals = the_coverage.get_result(
            'allowed_amounts', {
                'date': self.start_date,
                'appliable_conditions_date':
                self.option.contract.appliable_conditions_date,
                },)[0]
        if vals:
            res = map(lambda x: (x, x),
                map(lambda x: self.currency.amount_as_string(x), vals))
            return [('', '')] + res
        return [('', '')]

    def get_with_coverage_amount(self, name):
        has_coverage_amount = len(self.get_possible_amounts()) > 1
        if not has_coverage_amount:
            return False
        if not self.get_coverage().get_result(
                'dependant_amount_coverage', {
                    'date': self.start_date,
                    'appliable_conditions_date':
                    self.option.contract.appliable_conditions_date,
                })[0]:
            return True
        return False

    def is_party_covered(self, party, at_date):
        return self.covered_element.is_party_covered(party, at_date,
            self.option)

    @classmethod
    def default_coverage_amount(cls):
        return None
