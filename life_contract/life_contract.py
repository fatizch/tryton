import copy

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


class LifeCoveredData(model.CoopSQL, CoveredData):
    'Covered Data'

    __name__ = 'life_contract.covered_data'

    amount = fields.Numeric('Covered Amount')

    @classmethod
    def __setup__(cls):
        super(LifeCoveredData, cls).__setup__()
        cls.for_covered = copy.copy(cls.for_covered)
        cls.for_covered.model_name = 'life_contract.covered_person'


class LifeCoveredDataDesc(CoveredDataDesc):
    'Covered Data'

    __name__ = 'life_contract.covered_data_desc'

    covered_amount_old = fields.Numeric('Covered Amount')
    covered_amount = fields.Selection(
        'get_allowed_amounts',
        context={'for_coverage': Eval('for_coverage')},
        depends=['for_coverage'])

    @classmethod
    def __setup__(cls):
        super(LifeCoveredDataDesc, cls).__setup__()
        cls.covered_element = copy.copy(cls.covered_element)
        cls.covered_element.model_name = 'life_contract.covered_person_desc'

    @staticmethod
    def get_allowed_amounts():
        coverage = Transaction().context.get('for_coverage')
        if not coverage:
            return []
        wizard = LifeCoveredDataDesc.get_context()
        the_coverage = utils.convert_ref_to_obj(coverage)
        vals, = the_coverage.get_result(
            'allowed_amounts',
            {'date': wizard.project.start_date},
            manager='coverage_amount'
            )
        return vals


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
                            'Covered Elements')

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
        for coverage in wizard.option_selection.options:
            if coverage.status == 'Active':
                covered_data = CoveredData()
                covered_data.status = 'Active'
                covered_data.init_from_coverage(coverage)
                covered_datas.append(covered_data)
        wizard.extension_life.covered_elements = []
        covered_person = CoveredPerson()
        covered_person.person = wizard.project.subscriber.person[0].id
        covered_person.covered_data = covered_datas
        wizard.extension_life.covered_elements = [covered_person]
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
                cur_element.covered_data.append(cur_data)
            cur_element.person = covered_element.person
            ext.covered_elements.append(cur_element)

        contract.extension_life = [ext]
        res = contract.check_sub_elem_eligibility(
            wizard.project.start_date,
            'extension_life')
        if res[0]:
            utils.WithAbstract.save_abstract_objects(
                wizard, ('for_contract', contract))
        return res


class SubscriptionProcess():
    'Subscription Process'

    __metaclass__ = PoolMeta

    __name__ = 'ins_contract.subs_process'

    extension_life = CoopStateView(
        'life_contract.extension_life_state',
        'life_contract.extension_life_view')

    def give_covered_data_desc_model(self):
        return 'life_contract.covered_data_desc'
