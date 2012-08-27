import datetime

from trytond.model import fields as fields

# Needed for getting models
from trytond.pool import Pool

# Needed for Evaluation
from trytond.pyson import Eval

from trytond.modules.insurance_process import CoopProcess
from trytond.modules.insurance_process import ProcessState
from trytond.modules.insurance_process import CoopStep
from trytond.modules.insurance_process import CoopStateView
from trytond.modules.insurance_process import DependantState
from trytond.modules.insurance_process import CoopStepView

from trytond.modules.coop_utils import get_descendents, WithAbstract

from contract import OPTIONSTATUS

from trytond.modules.insurance_product import Coverage

###############################################################################
# This is the Subscription Process. It is a process (which uses the           #
# CoopProcess framework) which allows to create a contract from scratch.      #
# It asks first for a product, then uses it to calculate things like          #
# eligibility to decide which options will be offered, then finally           #
# creates the contract.                                                       #
###############################################################################

__all__ = [
        'ProjectState',
        'CoverageDisplayer',
        'OptionSelectionState',
        'CoveredDataDesc',
        'CoveredPersonDesc',
        'ExtensionLifeState',
        'SubscriptionProcessState',
        'SubscriptionProcess',
        'SummaryState',
        'PricingLine'
           ]


class ProjectState(CoopStep):
    '''
        This step should be the first one, as it asks the user which product
        the contract will be based on, and who will be the client.
    '''
    __name__ = 'ins_contract.subs_process.project'

    # This will be the effective date of our contract. It is necessary to have
    # it at this step for it decides which product will be available.
    start_date = fields.Date('Effective Date')

    # The subscriber is the client which wants to subscribe to a contract.
    subscriber = fields.Many2One('party.party',
                                 'Subscriber')

    # This is a core field, it will be used all along the process to ask for
    # directions, client side rules, etc...
    product = fields.Many2One('ins_product.product',
                              'Product',
                              # domain : a list of conditions
                              # (param1, op, param2).
                              # Param1 must be a field of the target model,
                              # Param2 will be evaluated in the current record
                              # context, so will return the value of
                              # start_date in the current ProjetState
                              domain=[('start_date',
                                       '<=',
                                       Eval('start_date', None))],
                              depends=['start_date', ],
                              states={'invisible': ~Eval('start_date')})

    broker = fields.Many2One('party.party',
                             'Broker',
                             states={'invisible': ~Eval('product')})

    # Default start_date is today
    @staticmethod
    def before_step_init(wizard):
        if not hasattr(wizard.project, 'start_date'):
            wizard.project.start_date = datetime.date.today()
        return (True, [])

    @staticmethod
    def check_step_product(wizard):
        if not (hasattr(wizard.project, 'product') and wizard.project.product):
            return (False, ['A product must be provided !'])
        if not(hasattr(wizard.project, 'subscriber')
                and wizard.project.subscriber):
            return (True, [])
        eligibility, errors = wizard.project.product.get_result(
            'eligibility',
            {'subscriber': wizard.project.subscriber,
            'date': wizard.project.start_date})
        if eligibility:
            return (eligibility.eligible, eligibility.details + errors)
        return (True, [])

    @staticmethod
    def check_step_subscriber(wizard):
        if hasattr(wizard.project, 'subscriber') and wizard.project.subscriber:
            return (True, [])
        return (False, ['A subscriber must be provided !'])

    @staticmethod
    def check_step_effective_date(wizard):
        if hasattr(wizard.project, 'start_date') and wizard.project.start_date:
            return (True, [])
        return (False, ['An effective date is necessary'])

    @staticmethod
    def post_step_update_abstract(wizard):
        BrokerManager = Pool().get('ins_contract.broker_manager')
        contract = WithAbstract.get_abstract_objects(wizard, 'for_contract')
        contract.product = wizard.project.product
        contract.start_date = wizard.project.start_date
        contract.subscriber = wizard.project.subscriber
        if hasattr(wizard.project, 'broker'):
            broker_manager = BrokerManager()
            broker_manager.broker = wizard.project.broker
            contract.broker_manager = broker_manager
        WithAbstract.save_abstract_objects(wizard, ('for_contract', contract))
        return (True, [])

    @staticmethod
    def post_step_update_on_product(wizard):
        wizard.process_state.on_product = wizard.project.product.id
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Product Selection'


class CoverageDisplayer(CoopStepView):
    '''
        This class is a displayer, that is a class which will only be used
        to show something (or ask for something) to the user. It needs not
        to be stored, and is not supposed to be.
    '''
    __name__ = 'ins_contract.coverage_displayer'
    coverage = fields.Many2One('ins_product.coverage',
                                   'Coverage',
                                   readonly=True)
    start_date = fields.Date(
                        'From Date',
                        domain=[('coverage.start_date',
                                 '<=',
                                 'start_date')],
                        depends=['coverage', ],
                        required=True)
    status = fields.Selection(OPTIONSTATUS,
                              'Status')

    def init_from_coverage(self, for_coverage):
        self.coverage = for_coverage
        self.start_date = for_coverage.start_date
        self.status = 'Active'


class OptionSelectionState(CoopStep):
    '''
        This step uses the provided product to compute a list of available
        options and asks the user to select which one he wants to
        subscribe to.
    '''
    __name__ = 'ins_contract.subs_process.option_selection'

    # Those are the temporary fields that we will use to represent options.
    # There is no need to give origin and target values, as they are intended
    # solely to provide a way for the user to make his choice.
    options = fields.One2Many('ins_contract.coverage_displayer',
                               None,
                               'Options Choices')

    # We initialize the list of options with the list of coverages offered by
    # the product previously selected.
    @staticmethod
    def before_step_init_options(wizard):
        '''
            This method should not be called when coming from downstream.
            If its from upstream it should.

            Later, we might want to make the 'from upstream' call optionnal,
            depending of what has been changed, but right now we will settle
            for this.
        '''
        options = []
        # Here we assume that there is a step named 'project' with a 'product'
        # field.
        # Later, we might want to use some abstract way to get the product
        # (maybe a method parsing the wizard states to get one which would
        # match a specific pattern) in order to become state name independant.
        #
        # So we go through the options of our product, then create a displayer
        # which will be used to ask for input from the user.
        CoverageDisplayer = Pool().get(wizard.give_displayer_model())
        for coverage in wizard.project.product.options:
            cur_displayer = CoverageDisplayer()
            cur_displayer.init_from_coverage(coverage)
            cur_displayer.start_date = max(
                cur_displayer.start_date,
                wizard.project.start_date)
            options.append(cur_displayer)
        # Then set those displayers as the options field of our current step.
        wizard.option_selection.options = options
        return (True, [])

    @staticmethod
    def check_step_option_eligibility(wizard):
        errs = []
        eligible = True
        for displayer in wizard.option_selection.options:
            if displayer.status == 'Active':
                eligibility, errors = displayer.coverage.get_result(
                    'eligibility',
                    {'date': wizard.project.start_date,
                    'subscriber': wizard.project.subscriber})
                errs += eligibility.details + errors
                eligible = eligible and eligibility.eligible
        return (eligible, errs)

    # Here we check that at least one option has been selected
    @staticmethod
    def check_step_option_selected(wizard):
        for coverage in wizard.option_selection.options:
            if coverage.status == 'Active':
                return (True, [])
        return (False, ['At least one option must be active'])

    # and that all options must have an effective date greater than the
    # future contract's effective date.
    @staticmethod
    def check_step_options_date(wizard):
        for coverage in wizard.option_selection.options:
            if coverage.start_date < wizard.project.start_date:
                return (False, ['Options must be subscribed after %s'
                                 % wizard.project.start_date])
            elif coverage.start_date < coverage.coverage.start_date:
                return (False, ['%s must be subscribed after %s'
                                % (coverage.coverage.name,
                                   coverage.coverage.start_date)])
        return (True, [])

    @staticmethod
    def post_step_create_options(wizard):
        contract = WithAbstract.get_abstract_objects(wizard, 'for_contract')
        list_options = []
        Option = Pool().get(contract.give_option_model())
        for option in wizard.option_selection.options:
            if option.status != 'Active':
                continue
            cur_option = Option()
            cur_option.coverage = option.coverage
            cur_option.start_date = option.start_date
            list_options.append(cur_option)
        contract.options = list_options
        WithAbstract.save_abstract_objects(wizard, ('for_contract', contract))
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Options Selection'


class CoveredDataDesc(CoopStepView):
    '''
        This is a descriptor for the covered data element.
    '''
    __name__ = 'ins_contract.subs_process.covered_data_desc'
    covered_element = fields.Reference('Covered Element',
                                       selection='get_covered_elem_model')

    status = fields.Selection(OPTIONSTATUS, 'Status')

    start_date = fields.Date('Start Date')

    end_date = fields.Date('End Date')

    for_coverage = fields.Reference(
        'For coverage',
        'get_coverages_model')

    @staticmethod
    def get_covered_elem_model():
        return get_descendents(DependantState)

    @staticmethod
    def get_coverages_model():
        res = get_descendents(Coverage)
        res.append((Coverage.__name__, Coverage.__name__))
        return res

    def init_from_coverage(self, for_coverage):
        self.start_date = for_coverage.start_date
        self.for_coverage = for_coverage.coverage


class CoveredElementDesc(CoopStepView):
    '''
        This is a descriptor for the covered element.
    '''
    covered_data = fields.One2Many(
                            'ins_contract.subs_process.covered_data_desc',
                            'covered_element',
                            'Covered Data')

    @staticmethod
    def default_covered_data():
        from_wizard = CoveredPersonDesc.get_context()
        contract = WithAbstract.get_abstract_objects(from_wizard,
                                                     'for_contract')
        covered_datas = []
        CoveredDataDesc = Pool().get(
            from_wizard.give_covered_data_desc_model())
        for covered in contract.options:
            covered_data = CoveredDataDesc()
            covered_data.init_from_coverage(covered)
            covered_data.status = 'Active'
            covered_datas.append(covered_data)
        return WithAbstract.serialize_field(covered_datas)


class CoveredPersonDesc(CoveredElementDesc):
    '''
        This is a descriptor for a covered person.
    '''
    __name__ = 'ins_contract.subs_process.covered_person_desc'

    person = fields.Many2One('party.party',
                             'Covered Person')
    life_state = fields.Many2One('ins_contract.subs_process.extension_life',
                                 'Life State')


class ExtensionLifeState(DependantState):
    '''
        This a process step which will be used for Life product subscriptions.
    '''
    __name__ = 'ins_contract.subs_process.extension_life'
    covered_elements = fields.One2Many(
                            'ins_contract.subs_process.covered_person_desc',
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
        CoveredData = Pool().get(wizard.give_covered_data_desc_model())
        CoveredPerson = Pool().get(
            'ins_contract.subs_process.covered_person_desc')
        for coverage in wizard.option_selection.options:
            if coverage.status == 'Active':
                covered_data = CoveredData()
                covered_data.status = 'Active'
                covered_data.init_from_coverage(coverage)
                covered_datas.append(covered_data)
        wizard.extension_life.covered_elements = []
        covered_person = CoveredPerson()
        covered_person.person = wizard.project.subscriber.id
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
    def check_step_sub_elem_eligibility(wizard):
        contract = WithAbstract.get_abstract_objects(wizard, 'for_contract')
        options = dict([
            (option.coverage.code, option)
            for option in contract.options
            ])
        res, errs = (True, [])
        for covered_element in wizard.extension_life.covered_elements:
            for covered_data in covered_element.covered_data:
                if not hasattr(
                        covered_data,
                        'status') and covered_data.status == 'Active':
                    continue
                eligibility, errors = covered_data.for_coverage.get_result(
                    'sub_elem_eligibility',
                    {'date': wizard.project.start_date,
                    'person': covered_element.person,
                    'option': options[covered_data.for_coverage.code]})
                res = res and eligibility.eligible
                errs += eligibility.details
                errs += errors
        return (res, errs)

    @staticmethod
    def post_step_update_contract(wizard):
        contract = WithAbstract.get_abstract_objects(wizard, 'for_contract')
        ExtensionLife = Pool().get('ins_contract.extension_life')
        CoveredElement = Pool().get('ins_contract.covered_element')
        CoveredData = Pool().get('ins_contract.covered_data')
        CoveredPerson = Pool().get('ins_contract.covered_person')
        if hasattr(contract, 'extension_life'):
            ext = ExtensionLife(contract.extension_life)
            CoveredElement.delete(ext.covered_elements)
        else:
            ext = ExtensionLife()
        ext.covered_elements = []
        for covered_element in wizard.extension_life.covered_elements:
            cur_element = CoveredElement()
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
            cur_person = CoveredPerson()
            cur_person.person = covered_element.person
            cur_person.save()
            cur_element.product_specific = '%s,%s' % (cur_person.__name__,
                                                      cur_person.id)
            ext.covered_elements.append(cur_element)

        ext.save()
        contract.extension_life = ext
        WithAbstract.save_abstract_objects(wizard, ('for_contract', contract))
        return (True, [])


class PricingLine(CoopStepView):
    'Pricing Line'
    # This class is a displayer for pricing data. It is supposed to be
    # displayed as a list.

    __name__ = 'ins_contract.subs_process.lines'

    summary_state = fields.Many2One(
        'ins_contract.subs_process.summary',
        'State')

    name = fields.Char('Name')

    value = fields.Numeric('Value')

    @staticmethod
    def create_from_result(result, prefix=''):
        # result is a PricingLineResult instance
        top_line = PricingLine()
        top_line.name = prefix + result.name
        top_line.value = result.value
        res = [top_line]
        for elem in result.desc:
            res += PricingLine.create_from_result(elem, prefix + '\t')
        return res


class SummaryState(CoopStep):
    'Summary'
    # This class describes a view which will be used to display a summary of
    # the subscription process just before the finalization of the subscription

    __name__ = 'ins_contract.subs_process.summary'

    lines = fields.One2Many(
        'ins_contract.subs_process.lines',
        'summary_state',
        'Lines')

    @staticmethod
    def before_step_calculate_lines(wizard):
        PricingLine = Pool().get('ins_contract.subs_process.lines')
        contract = WithAbstract.get_abstract_objects(wizard, 'for_contract')

        prices, errs = contract.calculate_prices_at_all_dates()

        if errs:
            return (False, errs)
        wizard.summary.lines = []
        for key, value in prices.iteritems():
            line = PricingLine()
            line.name = key
            wizard.summary.lines.append(line)
            other_lines = PricingLine.create_from_result(value, '\t')
            wizard.summary.lines += other_lines
            line = PricingLine()
            wizard.summary.lines.append(line)
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Summary'


class SubscriptionProcessState(ProcessState, WithAbstract):
    '''
        The process state for the subscription process must have an abstract
        contract.
    '''
    __abstracts__ = [('for_contract', 'ins_contract.contract')]
    __name__ = 'ins_contract.subs_process.process_state'


class SubscriptionProcess(CoopProcess):
    '''
        This class defines the subscription process. It asks the user all that
        will be needed to finally create a contract.
    '''
    __name__ = 'ins_contract.subs_process'

    config_data = {
        'process_state_model': 'ins_contract.subs_process.process_state'
        }

    # Here we just have to declare our steps
    project = CoopStateView(
        'ins_contract.subs_process.project',
        'insurance_contract.project_view')
    option_selection = CoopStateView(
        'ins_contract.subs_process.option_selection',
        'insurance_contract.option_selection_view')
    extension_life = CoopStateView(
        'ins_contract.subs_process.extension_life',
        'insurance_contract.extension_life_view')

    summary = CoopStateView(
        'ins_contract.subs_process.summary',
        'insurance_contract.summary_view')

    # And do something when validation occurs
    def do_complete(self):
        contract = WithAbstract.get_abstract_objects(self, 'for_contract')
        Contract = Pool().get(contract.__name__)

        contract.contract_number = contract.get_new_contract_number()

        if not (hasattr(contract, 'billing_manager') and
                contract.billing_manager):
            BillingManager = Pool().get(contract.get_manager_model())
            bm = BillingManager()
            contract.billing_manager = [bm]

        contract.save()

        contract = Contract(contract.id)

        # We need to recalculate the pricing in order to be able to set the
        # links with the covered elements

        prices, errs = contract.calculate_prices_at_all_dates()

        if errs:
            return (False, errs)

        contract.billing_manager[0].store_prices(prices)

        contract.billing_manager[0].save()

        # Do not forget to return a 'everything went right' signal !
        return (True, [])

    def give_displayer_model(self):
        return 'ins_contract.coverage_displayer'

    def give_covered_data_desc_model(self):
        return 'ins_contract.subs_process.covered_data_desc'

    @staticmethod
    def coop_process_name():
        return 'Subscription Process'
