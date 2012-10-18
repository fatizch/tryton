import copy
import datetime
from decimal import Decimal

from trytond.model import fields as fields

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model as model
from trytond.modules.coop_utils import utils as utils

from trytond.modules.insurance_contract import GenericExtension
from trytond.modules.insurance_contract import CoveredElement
from trytond.modules.insurance_contract import CoveredData
from trytond.modules.insurance_contract import CoveredElementDesc
from trytond.modules.insurance_contract import CoveredDataDesc
from trytond.modules.insurance_process import DependantState
from trytond.modules.insurance_process import CoopStateView


__all__ = ['Contract', 'ExtensionLife', 'CoveredPerson',
    'LifeCoveredData', 'LifeCoveredDataDesc', 'LifeCoveredPersonDesc',
    'ExtensionLifeState', 'SubscriptionProcess']


class Contract():
    'Contract'

    __metaclass__ = PoolMeta

    __name__ = 'ins_contract.contract'

    extension_life = fields.One2Many(
        'life_contract.extension',
        'contract',
        'Life Extension',
        size=1)

    def check_covered_amounts(self, at_date, ext):
        options = dict([
            (option.coverage.code, option)
            for option in self.options
            ])
        res, errs = (True, [])
        for covered_element in getattr(self, ext)[0].covered_elements:
            for covered_data in covered_element.covered_data:
                if (covered_data.start_date > at_date
                        or hasattr(covered_data, 'end_date') and
                        covered_data.end_date and
                        covered_data.end_date > at_date):
                    continue
                validity, errors = covered_data.for_coverage.get_result(
                    'coverage_amount_validity',
                    {'date': at_date,
                    'sub_elem': covered_element,
                    'data': covered_data,
                    'option': options[covered_data.for_coverage.code],
                    'contract': self})
                res = res and validity[0]
                errs += validity[1]
                errs += errors
        return (res, errs)


class ExtensionLife(model.CoopSQL, GenericExtension):
    '''
        This is a particular case of contract extension designed for Life
        insurance products.
    '''
    __name__ = 'life_contract.extension'

    @classmethod
    def __setup__(cls):
        super(ExtensionLife, cls).__setup__()
        cls.covered_elements = copy.copy(cls.covered_elements)
        cls.covered_elements.model_name = 'life_contract.covered_person'

    @staticmethod
    def get_covered_element_model():
        return 'life_contract.covered_person'


class CoveredPerson(model.CoopSQL, CoveredElement):
    'Covered Person'
    '''
        This is an extension of covered element in the case of a life product.

        In life insurance, we cover persons, so here is a covered person...
    '''
    __name__ = 'life_contract.covered_person'

    person = fields.Many2One('party.person',
                             'Person',
                             required=True)

    @classmethod
    def __setup__(cls):
        super(CoveredPerson, cls).__setup__()
        cls.extension = copy.copy(cls.extension)
        cls.extension.model_name = 'life_contract.extension'
        cls.covered_data = copy.copy(cls.covered_data)
        cls.covered_data.model_name = 'life_contract.covered_data'

    @staticmethod
    def get_specific_model_name():
        return 'Covered Person'

    def get_name_for_billing(self):
        return self.person.name

    def get_name_for_info(self):
        return self.person.name

    def get_rec_name(self, value):
        return self.person.name


#
#  This code was added as a test to check that step_over could allow to
#  totally jump over a step
#
#class OptionSelectionStateLife():
#    'Option Selection State'
#    __metaclass__ = PoolMeta
#    __name__ = 'ins_contract.subs_process.option_selection'
#
#    @staticmethod
#    def step_over_test(wizard):
#        return True, []


class LifeCoveredData(model.CoopSQL, CoveredData):
    'Covered Data'

    __name__ = 'life_contract.covered_data'

    coverage_amount = fields.Numeric('Coverage Amount')

    @classmethod
    def __setup__(cls):
        super(LifeCoveredData, cls).__setup__()
        cls.for_covered = copy.copy(cls.for_covered)
        cls.for_covered.model_name = 'life_contract.covered_person'


class LifeCoveredDataDesc(CoveredDataDesc):
    'Covered Data'

    __name__ = 'life_contract.covered_data_desc'

    coverage_amount = fields.Selection(
        'get_allowed_amounts',
        'Coverage Amount',
        context={'for_coverage': Eval('for_coverage')},
        depends=['for_coverage'],
        sort=False)

    @classmethod
    def __setup__(cls):
        super(LifeCoveredDataDesc, cls).__setup__()
        cls.covered_element = copy.copy(cls.covered_element)
        cls.covered_element.model_name = 'life_contract.covered_person_desc'

    @staticmethod
    def get_allowed_amounts():
        print datetime.datetime.now(), 'calculating get_allowed_amounts'
        try:
            coverage = Transaction().context.get('for_coverage')
            if not coverage:
                return []
            wizard = LifeCoveredDataDesc.get_context()
            the_coverage = utils.convert_ref_to_obj(coverage)
            vals = the_coverage.get_result(
                'allowed_amounts',
                {
                    'date': wizard.project.start_date,
                    'contract': utils.WithAbstract.get_abstract_objects(
                        wizard, 'for_contract')},)[0]
            return map(lambda x: (x, x), map(lambda x: '%.2f' % x, vals))
        except:
            return []


class LifeCoveredPersonDesc(CoveredElementDesc):
    'Covered Person'
    '''
        This is a descriptor for a covered person.
    '''
    __name__ = 'life_contract.covered_person_desc'

    person = fields.Many2One('party.person',
                             'Covered Person')
    life_state = fields.Many2One('life_contract.extension_life_state',
                                 'Life State')

    @classmethod
    def __setup__(cls):
        super(LifeCoveredPersonDesc, cls).__setup__()
        cls.covered_data = copy.copy(cls.covered_data)
        cls.covered_data.model_name = 'life_contract.covered_data_desc'


class ExtensionLifeState(DependantState):
    'Life Extension'
    '''
        This a process step which will be used for Life product subscriptions.
    '''
    __name__ = 'life_contract.extension_life_state'
    covered_elements = fields.One2Many(
        'life_contract.covered_person_desc',
        'life_state',
        'Covered Elements',
        context={
            'for_product': Eval('for_product'),
            'at_date': Eval('at_date')})
    dynamic_data = fields.Dict(
        'Dynamic Data',
        schema_model='ins_product.schema_element',
        context={
            'for_product': Eval('for_product'),
            'at_date': Eval('at_date'),
            'dd_args': {
                'options': Eval('for_options'),
                'kind': 'main',
                'path': 'extension_life'}},
        depends=['for_product', 'at_date', 'for_options'],
        states={'invisible': ~Eval('for_product')})
    for_product = fields.Many2One(
        'ins_product.product',
        'For Product',
        states={'invisible': True})
    at_date = fields.Date(
        'At Date',
        states={'invisible': True})
    for_options = fields.Char('For Options', states={'invisible': True})

    @staticmethod
    def depends_on_state():
        return 'extension'

    @staticmethod
    def state_name():
        return 'extension_life'

    @staticmethod
    def before_step_subscriber_as_covered(wizard):
        covered_datas = []
        CoveredData = Pool().get('life_contract.covered_data_desc')
        CoveredPerson = Pool().get('life_contract.covered_person_desc')
#        for coverage in wizard.option_selection.options:
#            if coverage.status == 'Active':
#                covered_data = CoveredData()
#                covered_data.status = 'Active'
#                covered_data.init_from_coverage(coverage)
#                covered_datas.append(covered_data)
#        wizard.extension_life.covered_elements = []
        covered_person = CoveredPerson()
        covered_person.person = wizard.project.subscriber.person[0].id
        covered_person.covered_data = CoveredPerson.default_covered_data(
            from_wizard=wizard)
        wizard.extension_life.covered_elements = [covered_person]
        return (True, [])

    @staticmethod
    def before_step_init_dynamic_data(wizard):
        product = wizard.project.product
        options = ';'.join([opt.coverage.code
            for opt in wizard.option_selection.options
            if opt.status == 'Active'])
        wizard.extension_life.dynamic_data = utils.init_dynamic_data(
            product.get_result(
                'dynamic_data_getter',
                {
                    'date': wizard.project.start_date,
                    'dd_args': {
                        'options': options,
                        'kind': 'main',
                        'path': 'extension_life'}})[0])
        if wizard.extension_life.dynamic_data:
            wizard.extension_life.for_product = product
            wizard.extension_life.at_date = wizard.project.start_date
            wizard.extension_life.for_options = options
        return (True, [])

    @staticmethod
    def check_step_at_least_one_covered(wizard):
        if len(wizard.extension_life.covered_elements) == 0:
            return (False, ['There must be at least one covered person'])
        errors = []
        for covered_element in wizard.extension_life.covered_elements:
            found = False
            for covered_data in covered_element.covered_data:
                if hasattr(
                        covered_data,
                        'status') and covered_data.status == 'Active':
                    found = True
                    break
            if not found:
                errors.append('At least one option must be activated for %s'
                              % covered_element.person.name)
        if errors:
            return (False, errors)
        return (True, [])

    @staticmethod
    @utils.priority(0)
    def post_step_update_contract(wizard):
        contract = utils.WithAbstract.get_abstract_objects(
            wizard, 'for_contract')
        ExtensionLife = Pool().get('life_contract.extension')
        CoveredPerson = Pool().get('life_contract.covered_person')
        CoveredData = Pool().get('life_contract.covered_data')
        if hasattr(contract, 'extension_life') and contract.extension_life:
            ext = contract.extension_life[0]
        else:
            ext = ExtensionLife()
        ext.covered_elements = []
        for covered_element in wizard.extension_life.covered_elements:
            cur_element = CoveredPerson()
            cur_element.covered_data = []
            for covered_data in covered_element.covered_data:
                if covered_data.status != 'Active':
                    continue
                cur_data = CoveredData()
                cur_data.start_date = covered_data.start_date
                if hasattr(covered_data, 'end_date'):
                    cur_data.end_date = covered_data.end_date
                cur_data.for_coverage = covered_data.for_coverage
                if hasattr(covered_data, 'coverage_amount') and \
                        covered_data.coverage_amount:
                    try:
                        cur_data.coverage_amount = Decimal(
                            covered_data.coverage_amount)
                    except ValueError:
                        return False, ['Invalid amount']
                else:
                    cur_data.coverage_amount = Decimal(0)
                cur_element.covered_data.append(cur_data)
            cur_element.person = covered_element.person
            ext.covered_elements.append(cur_element)

        contract.extension_life = [ext]
        res = contract.check_sub_elem_eligibility(
            wizard.project.start_date,
            'extension_life')
        if res[0]:
            res1 = contract.check_covered_amounts(
                wizard.project.start_date,
                'extension_life')
        else:
            return res
        if res[0] and res1[0]:
            utils.WithAbstract.save_abstract_objects(
                wizard, ('for_contract', contract))
            return res[0] * res1[0], res[1] + res1[1]
        else:
            return res1


class SubscriptionProcess():
    'Subscription Process'

    __metaclass__ = PoolMeta

    __name__ = 'ins_contract.subs_process'

    extension_life = CoopStateView(
        'life_contract.extension_life_state',
        'life_contract.extension_life_view')

    def give_covered_data_desc_model(self):
        return 'life_contract.covered_data_desc'
