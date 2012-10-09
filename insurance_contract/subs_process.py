from trytond.model import fields as fields

# Needed for getting models
from trytond.pool import Pool

# Needed for Evaluation
from trytond.pyson import Eval

from trytond.modules.insurance_process import CoopProcess
from trytond.modules.insurance_process import ProcessState
from trytond.modules.insurance_process import CoopStep
from trytond.modules.insurance_process import CoopStateView
from trytond.modules.insurance_process import CoopStepView

from trytond.modules.coop_utils import get_descendents, WithAbstract
from trytond.modules.coop_party import ACTOR_KIND

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
        'CoveredElementDesc',
        'SummaryState',
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

    subscriber_kind = fields.Selection(ACTOR_KIND, 'Kind',
        on_change=['subscriber_as_person', 'subscriber_as_person',
            'subscriber_kind'])
    # The subscriber is the client which wants to subscribe to a contract.
    subscriber = fields.Many2One('party.party', 'Subscriber',
        on_change_with=['subscriber_as_person', 'subscriber_as_company',
            'subscriber_kind']
        )
    subscriber_as_person = fields.Many2One('party.person', 'Subscriber',
        states={'invisible': Eval('subscriber_kind') != 'party.person',
            })
    subscriber_as_company = fields.Many2One('company.company', 'Subscriber',
        states={'invisible': Eval('subscriber_kind') != 'company.company'})

    subscriber_desc = fields.Function(fields.Text('Summary',
            on_change_with=['subscriber_as_person', 'subscriber_as_company',
                'subscriber']),
        'on_change_with_subscriber_desc')

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

    product_desc = fields.Function(fields.Text('Description',
            on_change_with=['product']),
        'on_change_with_product_desc')

    broker = fields.Many2One('party.party',
                             'Broker')

    # Default start_date is today
    @staticmethod
    def before_step_init(wizard):
        Date = Pool().get('ir.date')
        if not hasattr(wizard.project, 'start_date'):
            wizard.project.start_date = Date.today()
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

    def on_change_with_product_desc(self):
        res = ''
        if self.product:
            res = self.product.description
        return res

    def on_change_with_subscriber_desc(self):
        res = ''
        if self.subscriber:
            res = self.subscriber.summary
        return res

    def on_change_with_subscriber(self):
        if (self.subscriber_as_person
                and self.subscriber_kind == 'party.person'):
            return self.subscriber_as_person.party.id
        elif (self.subscriber_as_company
                and self.subscriber_kind == 'company.company'):
            return self.subscriber_as_company.party.id

    def on_change_subscriber_kind(self):
        res = {}
        if self.subscriber_kind == 'party.person':
            res['subscriber_as_company'] = None
        elif self.subscriber_kind == 'company.company':
            res['subscriber_as_person'] = None
        return res

    @staticmethod
    def default_subscriber_kind():
        return 'party.person'


class CoverageDisplayer(CoopStepView):
    '''
        Coverage Description
    '''
    # This class is a displayer, that is a class which will only be used
    # to show something (or ask for something) to the user. It needs not
    # to be stored, and is not supposed to be.

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
                if not eligibility.eligible:
                    errs.append(
                        '%s option not eligible :' % displayer.coverage.code)
                    errs += ['\t' + elem
                        for elem in eligibility.details + errors]
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
    'Covered Data'
    '''
        This is a descriptor for the covered data element.
    '''
    __name__ = 'ins_contract.subs_process.covered_data_desc'

    covered_element = fields.Many2One(
        'ins_contract.subs_process.covered_element_desc',
        'Covered Element')

    status = fields.Selection(OPTIONSTATUS, 'Status')

    start_date = fields.Date('Start Date')

    end_date = fields.Date('End Date')

    for_coverage = fields.Reference(
        'For coverage',
        'get_coverages_model',
        readonly=True)

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

    __name__ = 'ins_contract.subs_process.covered_element'

    covered_data = fields.One2Many(
                            'ins_contract.subs_process.covered_data_desc',
                            'covered_element',
                            'Covered Data')

    @staticmethod
    def default_covered_data():
        from_wizard = CoveredElementDesc.get_context()
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

    taxes = fields.Numeric('Taxes')

    childs = fields.One2Many(
        'ins_contract.subs_process.lines',
        None,
        'Details')

    @staticmethod
    def create_from_result(result):
        # result is a PricingLineResult instance
        top_line = PricingLine()
        top_line.name = result.name
        top_line.value = result.value
        if not result.is_detail_alone('tax'):
            top_line.taxes = result.get_total_detail('tax')
        top_line.childs = []
        for elem in result.desc:
            top_line.childs.append(PricingLine.create_from_result(elem))
        return top_line

    @staticmethod
    def default_taxes():
        return 0

    @staticmethod
    def default_value():
        return 0


class SummaryState(CoopStep):
    'Summary'
    # This class describes a view which will be used to display a summary of
    # the subscription process just before the finalization of the subscription

    __name__ = 'ins_contract.subs_process.summary'

    lines = fields.One2Many(
        'ins_contract.subs_process.lines',
        'summary_state',
        'Lines',
        readonly=True)

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
            line.value = 0
            line.taxes = 0
            line.childs = []
            for val in value:
                sub_line = PricingLine.create_from_result(val)
                line.childs.append(sub_line)
                line.value += sub_line.value
                line.taxes += sub_line.taxes
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

    summary = CoopStateView(
        'ins_contract.subs_process.summary',
        'insurance_contract.summary_view')

    # And do something when validation occurs
    def do_complete(self):
        contract = WithAbstract.get_abstract_objects(self, 'for_contract')
        Contract = Pool().get(contract.__name__)

        contract.finalize_contract()

        if not (hasattr(contract, 'billing_manager') and
                contract.billing_manager):
            BillingManager = Pool().get(contract.get_manager_model())
            bm = BillingManager()
            contract.billing_manager = [bm]

        contract.status = 'active'

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

    @staticmethod
    def coop_process_name():
        return 'Subscription Process'

    def give_covered_data_desc_model(self):
        raise NotImplementedError
