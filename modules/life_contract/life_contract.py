import copy
from decimal import Decimal

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.rpc import RPC

from trytond.modules.coop_utils import utils, fields, abstract, coop_string

__all__ = [
    'Contract',
    'LifeOption',
    'CoveredPerson',
    'LifeCoveredData',
    'PriceLine',
]


class Contract():
    'Contract'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

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
            contract = cov_elem.get_contract()
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
    __metaclass__ = PoolMeta

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
    __metaclass__ = PoolMeta

    @classmethod
    def get_line_target_models(cls):
        res = super(PriceLine, cls).get_line_target_models()
        res.append(('life_contract.covered_data',
            'life_contract.covered_data'))
        return res


class CoveredPerson():
    'Covered Person'
    '''
        In life, covered item is a covered person
    '''

    __name__ = 'ins_contract.covered_element'
    __metaclass__ = PoolMeta


class LifeCoveredData():
    'Covered Data'

    __name__ = 'ins_contract.covered_data'
    __metaclass__ = PoolMeta

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


# class LifeCoveredDesc(CoveredDesc):
#     'Covered Desc'

#     __name__ = 'life_contract.covered_desc'

#     data_coverage_amount = fields.Selection(
#         'get_possible_amounts', 'Coverage Amount',
#         selection_change_with=['data_for_coverage', 'data_start_date'],
#         # context={'data_for_coverage': Eval('data_for_coverage')},
#         depends=['data_for_coverage', 'data_start_date'], sort=False,
#         states={
#             'readonly': Eval('the_kind') != 'data'})
#     elem_person = fields.Many2One(
#         'party.party', 'Covered Person',
#         depends=['data_coverage_name'], on_change=['elem_person'])
#     elem_life_state = fields.Many2One(
#         'life_contract.extension_life_state',
#         'Life State')

#     @classmethod
#     def __setup__(cls):
#         super(LifeCoveredDesc, cls).__setup__()
#         cls.data_covered_element = copy.copy(cls.data_covered_element)
#         cls.data_covered_element.model_name = \
#             'life_contract.covered_desc'
#         cls.elem_covered_data = copy.copy(cls.elem_covered_data)
#         cls.elem_covered_data.model_name = \
#             'life_contract.covered_desc'
#         cls.__rpc__.update({
#                 'get_possible_amounts': RPC(instantiate=0),
#         })

#     def on_change_elem_person(self):
#         if hasattr(self, 'elem_person') and self.elem_person:
#             return {'data_coverage_name': self.elem_person.get_rec_name('')}
#         return {}

#     def get_possible_amounts(self):
#         if not (hasattr(self, 'data_for_coverage') and self.data_for_coverage):
#             return []
#         the_coverage = utils.convert_ref_to_obj(self.data_for_coverage)
#         vals = the_coverage.get_result(
#             'allowed_amounts',
#             {
#                 'date': self.data_start_date,
#                 #'contract': abstract.WithAbstract.get_abstract_objects(
#                 #    wizard, 'for_contract')
#             },)[0]
#         if vals:
#             return map(lambda x: (x, x),
#                 map(lambda x: coop_string.amount_as_string(x,
#                     self.get_currency()), vals))
#         return ''


# class ExtensionLifeState(DependantState):
#     'Life Extension'
#     '''
#         This a process step which will be used for Life product subscriptions.
#     '''
#     __name__ = 'life_contract.extension_life_state'
#     covered_elements = fields.One2Many(
#         #'life_contract.covered_person_desc',
#         'life_contract.covered_desc',
#         'life_state',
#         'Covered Elements',
#         context={
#             'for_product': Eval('for_product'),
#             'at_date': Eval('at_date'),
#             'kind': 'elem'},
#         depends=['covered_elements'])
#     complementary_data = fields.Dict(
#         'ins_product.complementary_data_def', 'Complementary Data',
#         context={
#             'for_product': Eval('for_product'),
#             'at_date': Eval('at_date'),
#             'dd_args': {
#                 'options': Eval('for_options'),
#                 'kind': 'main',
#                 'path': 'extension_life'}},
#         depends=['for_product', 'at_date', 'for_options'],
#         states={'invisible': ~Eval('for_product')})
#     for_product = fields.Many2One(
#         'ins_product.product',
#         'For Product',
#         states={'invisible': True})
#     at_date = fields.Date(
#         'At Date',
#         states={'invisible': True})
#     for_options = fields.Char('For Options', states={'invisible': True})

#     @staticmethod
#     def depends_on_state():
#         return 'extension'

#     @staticmethod
#     def state_name():
#         return 'extension_life'

#     @staticmethod
#     def before_step_subscriber_as_covered(wizard):
#         contract = abstract.WithAbstract.get_abstract_objects(
#             wizard, 'for_contract')
#         if hasattr(wizard.extension_life, 'covered_elements') and \
#                 wizard.extension_life.covered_elements:
#             # Later, an update procedure should be written.
#             options = [o.offered.code for o in contract.options]
#             for elem in wizard.extension_life.covered_elements:
#                 for data in elem.elem_covered_data:
#                     if not data.data_for_coverage.code in options:
#                         elem.elem_covered_data.remove(data)
#             return True, []
#         CoveredDesc = Pool().get('life_contract.covered_desc')
#         covered_person = CoveredDesc()
#         covered_person.the_kind = 'elem'
#         with Transaction().set_context({
#                 'kind': 'elem'}):
#             covered_person.elem_covered_data = \
#                 CoveredDesc.default_elem_covered_data(wizard)
#         covered_person.elem_person = wizard.project.subscriber.id
#         covered_person.data_coverage_name = \
#             covered_person.elem_person.get_rec_name('')
#         wizard.extension_life.covered_elements = [covered_person]
#         return (True, [])

#     @staticmethod
#     def before_step_init_complementary_data(wizard):
#         product = wizard.project.product
#         options = ';'.join([opt.offered.code
#             for opt in wizard.option_selection.options
#             if opt.status == 'active'])
#         wizard.extension_life.complementary_data = \
#             utils.init_complementary_data_from_ids(
#                 product.get_result(
#                     'complementary_data_getter', {
#                         'date': wizard.project.start_date,
#                         'dd_args': {
#                             'options': options,
#                             'kind': 'main',
#                             'path': 'extension_life',
#                         }
#                     })[0])
#         if wizard.extension_life.complementary_data:
#             wizard.extension_life.for_product = product
#             wizard.extension_life.at_date = wizard.project.start_date
#             wizard.extension_life.for_options = options
#         return (True, [])

#     @staticmethod
#     def check_step_at_least_one_covered(wizard):
#         if len(wizard.extension_life.covered_elements) == 0:
#             return (False, ['There must be at least one covered person'])
#         errors = []
#         for covered_element in wizard.extension_life.covered_elements:
#             found = False
#             for covered_data in covered_element.elem_covered_data:
#                 if hasattr(covered_data, 'data_status') and \
#                         covered_data.data_status:
#                     found = True
#                     break
#             if not found:
#                 errors.append('At least one option must be activated for %s'
#                               % covered_element.elem_person.name)
#         if errors:
#             return (False, errors)
#         return (True, [])

#     @staticmethod
#     @utils.priority(0)
#     def post_step_update_contract(wizard):
#         contract = abstract.WithAbstract.get_abstract_objects(
#             wizard, 'for_contract')
#         CoveredPerson = Pool().get('ins_contract.covered_element')
#         CoveredData = Pool().get('ins_contract.covered_data')
#         contract.covered_elements = []
#         for covered_element in wizard.extension_life.covered_elements:
#             cur_element = CoveredPerson()
#             cur_element.covered_data = []
#             for covered_data in covered_element.elem_covered_data:
#                 if not covered_data.data_status:
#                     continue
#                 cur_data = CoveredData()
#                 cur_data.start_date = covered_data.data_start_date
#                 if hasattr(covered_data, 'data_end_date'):
#                     cur_data.end_date = covered_data.data_end_date
#                 cur_data.coverage = covered_data.data_for_coverage
#                 if hasattr(covered_data, 'data_coverage_amount') and \
#                         covered_data.data_coverage_amount:
#                     try:
#                         cur_data.coverage_amount = Decimal(
#                             covered_data.data_coverage_amount)
#                     except ValueError:
#                         return False, ['Invalid amount']
#                 else:
#                     cur_data.coverage_amount = Decimal(0)
#                 if hasattr(covered_data, 'data_complementary_data') and \
#                         covered_data.data_complementary_data:
#                     cur_data.complementary_data = \
#                         covered_data.data_complementary_data
#                 cur_element.covered_data.append(cur_data)
#             cur_element.party = covered_element.elem_person
#             contract.covered_elements.append(cur_element)

#         res = contract.check_sub_elem_eligibility(wizard.project.start_date)
#         if res[0]:
#             res1 = contract.check_covered_amounts(wizard.project.start_date)
#         else:
#             return res
#         if res[0] and res1[0]:
#             abstract.WithAbstract.save_abstract_objects(
#                 wizard, ('for_contract', contract))
#             return res[0] * res1[0], res[1] + res1[1]
#         else:
#             return res1


# class SubscriptionProcess():
#     'Subscription Process'

#     __metaclass__ = PoolMeta

#     __name__ = 'ins_contract.subs_process'

#     extension_life = CoopStateView(
#         'life_contract.extension_life_state',
#         'life_contract.extension_life_view')

#     def give_covered_data_desc_model(self):
#         return 'life_contract.covered_desc'
