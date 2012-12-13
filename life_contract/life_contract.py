import copy
from decimal import Decimal

from trytond.model import fields

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model
from trytond.modules.coop_utils import utils

from trytond.modules.insurance_contract import GenericExtension
from trytond.modules.insurance_contract import CoveredDesc
from trytond.modules.insurance_contract import CoveredData
from trytond.modules.insurance_contract import CoveredElement
from trytond.modules.insurance_process import DependantState
from trytond.modules.insurance_process import CoopStateView


__all__ = [
    'Contract',
    'ExtensionLife',
    'CoveredPerson',
    'LifeCoveredData',
    'LifeCoveredDesc',
    'ExtensionLifeState',
    'SubscriptionProcess',
    ]


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

    def init_extension_life(self):
        if not self.extension_life:
            return True, ()

        the_ext = self.extension_life[0]

        CoveredElement = Pool().get(the_ext.get_covered_element_model())
        CoveredData = Pool().get(CoveredElement.get_covered_data_model())

        if not self.extension_life.covered_elements:
            subscriber = CoveredElement()
            subscriber.init_from_person(self.subscriber_as_person)

        options = dict([(o.coverage.code, o) for o in self.options])

        for elem in the_ext.covered_elements:
            existing_datas = dict([(data.for_coverage.code, data)
                for data in elem.covered_data])

            elem.covered_data = []

            to_delete = [data for data in existing_datas.itervalues()]

            good_datas = []
            for code, option in options:
                if code in existing_datas:
                    good_datas.append(existing_datas[code])
                    to_delete.remove(existing_datas[code])
                    continue
                else:
                    good_data = CoveredData()
                    good_data.init_from_coverage(option.coverage)
                    good_data.start_date = max(
                        good_data.start_date, self.start_date)
                    with Transaction().set_context({
                            'current_contract': self.id}):
                        good_data.init_dynamic_data(option.coverage, self)
                    good_data.status_selection = True
                    good_datas.append(good_data)

            CoveredData.remove(to_delete)

            elem.covered_data = good_datas


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

    @classmethod
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
        return self.person.rec_name

    def get_name_for_info(self):
        return self.person.rec_name

    def get_rec_name(self, value):
        return self.person.rec_name

    @classmethod
    def get_covered_data_model(cls):
        return 'life_contract.covered_data'

    def init_from_person(self, person):
        self.person = person


class LifeCoveredData(model.CoopSQL, CoveredData):
    'Covered Data'

    __name__ = 'life_contract.covered_data'

    coverage_amount = fields.Numeric('Coverage Amount')

    @classmethod
    def __setup__(cls):
        super(LifeCoveredData, cls).__setup__()
        cls.for_covered = copy.copy(cls.for_covered)
        cls.for_covered.model_name = 'life_contract.covered_person'


class LifeCoveredDesc(CoveredDesc):
    'Covered Desc'

    __name__ = 'life_contract.covered_desc'

    data_coverage_amount = fields.Selection(
        'get_allowed_amounts',
        'Coverage Amount',
        context={'data_for_coverage': Eval('data_for_coverage')},
        depends=['data_for_coverage', 'start_date'],
        sort=False,
        states={
            'readonly': Eval('the_kind') != 'data'})

    elem_person = fields.Many2One(
        'party.person',
        'Covered Person',
        depends=['data_coverage_name'],
        on_change=['elem_person'])

    elem_life_state = fields.Many2One(
        'life_contract.extension_life_state',
        'Life State')

    @classmethod
    def __setup__(cls):
        super(LifeCoveredDesc, cls).__setup__()
        cls.data_covered_element = copy.copy(cls.data_covered_element)
        cls.data_covered_element.model_name = \
            'life_contract.covered_desc'
        cls.elem_covered_data = copy.copy(cls.elem_covered_data)
        cls.elem_covered_data.model_name = \
            'life_contract.covered_desc'

    def on_change_elem_person(self):
        if hasattr(self, 'elem_person') and self.elem_person:
            return {'data_coverage_name': self.elem_person.get_rec_name('')}
        return {}

    @staticmethod
    def get_allowed_amounts():
        try:
            coverage = Transaction().context.get('data_for_coverage')
            if not coverage:
                return []
            wizard = LifeCoveredDesc.get_context()
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


class ExtensionLifeState(DependantState):
    'Life Extension'
    '''
        This a process step which will be used for Life product subscriptions.
    '''
    __name__ = 'life_contract.extension_life_state'
    covered_elements = fields.One2Many(
#        'life_contract.covered_person_desc',
        'life_contract.covered_desc',
        'life_state',
        'Covered Elements',
        context={
            'for_product': Eval('for_product'),
            'at_date': Eval('at_date'),
            'kind': 'elem'},
        depends=['covered_elements'])
    dynamic_data = fields.Dict(
        'Complementary Data',
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
        contract = utils.WithAbstract.get_abstract_objects(
            wizard, 'for_contract')
        if hasattr(wizard.extension_life, 'covered_elements') and \
                wizard.extension_life.covered_elements:
            # Later, an update procedure should be written.
            options = [o.coverage.code for o in contract.options]
            for elem in wizard.extension_life.covered_elements:
                for data in elem.elem_covered_data:
                    if not data.data_for_coverage.code in options:
                        elem.elem_covered_data.remove(data)
            return True, []
        CoveredDesc = Pool().get('life_contract.covered_desc')
        covered_person = CoveredDesc()
        covered_person.the_kind = 'elem'
        with Transaction().set_context({
                'kind': 'elem'}):
            covered_person.elem_covered_data = \
                CoveredDesc.default_elem_covered_data(wizard)
        covered_person.elem_person = wizard.project.subscriber.person[0].id
        covered_person.data_coverage_name = \
            covered_person.elem_person.get_rec_name('')
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
            for covered_data in covered_element.elem_covered_data:
                if hasattr(covered_data, 'data_status') and \
                        covered_data.data_status == True:
                    found = True
                    break
            if not found:
                errors.append('At least one option must be activated for %s'
                              % covered_element.elem_person.name)
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
            for covered_data in covered_element.elem_covered_data:
                if covered_data.data_status != True:
                    continue
                cur_data = CoveredData()
                cur_data.start_date = covered_data.data_start_date
                if hasattr(covered_data, 'data_end_date'):
                    cur_data.end_date = covered_data.data_end_date
                cur_data.for_coverage = covered_data.data_for_coverage
                if hasattr(covered_data, 'data_coverage_amount') and \
                        covered_data.data_coverage_amount:
                    try:
                        cur_data.coverage_amount = Decimal(
                            covered_data.data_coverage_amount)
                    except ValueError:
                        return False, ['Invalid amount']
                else:
                    cur_data.coverage_amount = Decimal(0)
                if hasattr(covered_data, 'data_dynamic_data') and \
                        covered_data.data_dynamic_data:
                    cur_data.dynamic_data = covered_data.data_dynamic_data
                cur_element.covered_data.append(cur_data)
            cur_element.person = covered_element.elem_person
            ext.covered_elements.append(cur_element)

        if not(hasattr(ext, 'dynamic_data') and ext.dynamic_data):
            ext.dynamic_data = {}
        ext.dynamic_data.update(wizard.extension_life.dynamic_data)
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
        return 'life_contract.covered_desc'
