# Needed for getting models
from trytond.pool import Pool

# Needed for Evaluation
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.insurance_process import CoopProcess
from trytond.modules.insurance_process import ProcessState
from trytond.modules.insurance_process import CoopStep
from trytond.modules.insurance_process import CoopStateView
from trytond.modules.insurance_process import CoopStepView

from trytond.modules.coop_utils import utils, fields, abstract
from trytond.modules.coop_party.party import ACTOR_KIND

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
    'CoveredDesc',
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
    subscriber_as_person = fields.Many2One('party.party', 'Subscriber',
        states={'invisible': Eval('subscriber_kind') != 'person',
            }, domain=[('is_person', '=', True)])
    subscriber_as_company = fields.Many2One('party.party', 'Subscriber',
        states={'invisible': Eval('subscriber_kind') != 'company'},
        domain=[('is_company', '=', True)])

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
            {
                'subscriber': wizard.project.subscriber,
                'date': wizard.project.start_date
            })
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
        BrokerManager = Pool().get('ins_contract.management_role')
        contract = abstract.WithAbstract.get_abstract_objects(
            wizard, 'for_contract')
        contract.offered = wizard.project.product
        contract.start_date = wizard.project.start_date
        contract.subscriber = wizard.project.subscriber
        if hasattr(wizard.project, 'broker'):
            broker_manager = BrokerManager()
            broker_manager.party = wizard.project.broker
            contract.management = [broker_manager]
        abstract.WithAbstract.save_abstract_objects(
            wizard, ('for_contract', contract))
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
                and self.subscriber_kind == 'person'):
            return self.subscriber_as_person.id
        elif (self.subscriber_as_company
                and self.subscriber_kind == 'company'):
            return self.subscriber_as_company.id

    def on_change_subscriber_kind(self):
        res = {}
        if self.subscriber_kind == 'person':
            res['subscriber_as_company'] = None
        elif self.subscriber_kind == 'company':
            res['subscriber_as_person'] = None
        return res

    @staticmethod
    def default_subscriber_kind():
        return 'is_person'


class CoverageDisplayer(CoopStepView):
    '''
        Coverage Description
    '''
    # This class is a displayer, that is a class which will only be used
    # to show something (or ask for something) to the user. It needs not
    # to be stored, and is not supposed to be.

    __name__ = 'ins_contract.coverage_displayer'
    offered = fields.Many2One('ins_product.coverage', 'offered',
        readonly=True)
    start_date = fields.Date('From Date',
        domain=[('offered.start_date', '<=', 'start_date')],
        depends=['offered', ], required=True)
    status = fields.Selection(OPTIONSTATUS, 'Status')

    def init_from_coverage(self, coverage):
        self.offered = coverage
        self.start_date = coverage.start_date
        self.status = 'active'


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
    complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Complementary Data',
        context={
            'for_product': Eval('for_product'),
            'at_date': Eval('at_date'),
            'dd_args': {
                'kind': 'main'}},
        depends=['for_product', 'at_date'],
        states={'invisible': ~Eval('for_product')})
    for_product = fields.Many2One(
        'ins_product.product',
        'For Product',
        states={'invisible': True})
    at_date = fields.Date(
        'At Date',
        states={'invisible': True})

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
        product = wizard.project.product
        CoverageDisplayer = Pool().get(wizard.give_displayer_model())
        for offered in product.options:
            cur_displayer = CoverageDisplayer()
            cur_displayer.init_from_coverage(offered)
            cur_displayer.start_date = max(
                cur_displayer.start_date,
                wizard.project.start_date)
            options.append(cur_displayer)
        # Then set those displayers as the options field of our current step.
        wizard.option_selection.options = options
        return (True, [])

    @staticmethod
    def before_step_init_complementary_data(wizard):
        product = wizard.project.product
        wizard.option_selection.complementary_data = utils.init_complementary_data_from_ids(
            product.get_result(
                'complementary_data_getter',
                {
                    'date': wizard.project.start_date,
                    'dd_args': {
                        'kind': 'main'}})[0])
        if wizard.option_selection.complementary_data:
            wizard.option_selection.for_product = product
            wizard.option_selection.at_date = wizard.project.start_date
        return (True, [])

    @staticmethod
    def check_step_option_eligibility(wizard):
        errs = []
        eligible = True
        for displayer in wizard.option_selection.options:
            if displayer.status == 'active':
                eligibility, errors = displayer.offered.get_result(
                    'eligibility',
                    {'date': wizard.project.start_date,
                    'subscriber': wizard.project.subscriber})
                if eligibility and not eligibility.eligible:
                    errs.append(
                        '%s option not eligible :' % displayer.offered.code)
                    errs += ['\t' + elem
                        for elem in eligibility.details + errors]
                eligible = eligible and (not eligibility or
                        eligibility.eligible)
        return (eligible, errs)

    # Here we check that at least one option has been selected
    @staticmethod
    def check_step_option_selected(wizard):
        for offered in wizard.option_selection.options:
            if offered.status == 'active':
                return (True, [])
        return (False, ['At least one option must be active'])

    # and that all options must have an effective date greater than the
    # future contract's effective date.
    @staticmethod
    def check_step_options_date(wizard):
        for offered in wizard.option_selection.options:
            if offered.start_date < wizard.project.start_date:
                return (False, ['Options must be subscribed after %s'
                                 % wizard.project.start_date])
            elif offered.start_date < offered.offered.start_date:
                return (False, ['%s must be subscribed after %s'
                                % (offered.offered.name,
                                   offered.offered.start_date)])
        return (True, [])

    @staticmethod
    def post_step_create_options(wizard):
        contract = abstract.WithAbstract.get_abstract_objects(
            wizard, 'for_contract')
        list_options = []
        Option = Pool().get(contract.give_option_model())
        for option in wizard.option_selection.options:
            if option.status != 'active':
                continue
            cur_option = Option()
            cur_option.offered = option.offered
            cur_option.start_date = option.start_date
            list_options.append(cur_option)
        contract.options = list_options
        contract.complementary_data = {}
        if hasattr(wizard.option_selection, 'complementary_data') and \
                wizard.option_selection.complementary_data:
            contract.complementary_data.update(wizard.option_selection.complementary_data)
        abstract.WithAbstract.save_abstract_objects(
            wizard, ('for_contract', contract))
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Options Selection'

    @classmethod
    def default_get(cls, fields_names, with_rec_name=True):
        return super(OptionSelectionState, cls).default_get(
            fields_names, with_rec_name=with_rec_name)


class CoveredDesc(CoopStepView):
    'Covered Desc'
    '''
        This class is an attempt to unify CoveredDataDesc and
        CoveredElementDesc in order to be able to present both of these
        concepts in one tree view with child elements.
    '''

    __name__ = 'ins_contract.subs_process.covered_desc'

    the_kind = fields.Selection([
        ('elem', 'elem'),
        ('data', 'data'),
        ],
        'The kind',
        states={'invisible': True})

    elem_covered_data = fields.One2Many(
        'ins_contract.subs_process.covered_desc',
        'data_covered_element',
        'Covered Data',
        context={'kind': 'data'})

    data_covered_element = fields.Many2One(
        'ins_contract.subs_process.covered_desc',
        'Covered Element')

    data_status = fields.Boolean(
        'Status',
        states={
            'readonly': Eval('the_kind') != 'data'})

    data_start_date = fields.Date(
        'Start Date',
        states={
            'readonly': Eval('the_kind') != 'data'})

    data_end_date = fields.Date(
        'End Date',
        states={
            'readonly': Eval('the_kind') != 'data'})

    data_for_coverage = fields.Reference(
        'For offered',
        'get_coverages_model',
        readonly=True)

    data_coverage_name = fields.Char(
        'offered',
        depends=['data_for_coverage'],
        on_change_with=['data_for_coverage'],
        readonly=True)

    data_complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Complementary Data',
        context={
            'at_date': Eval('data_start_date'),
            'dd_args': {
                'options': Eval('data_for_option_char'),
                'kind': 'sub_elem'}},
        depends=['data_for_option_char', 'data_start_date'])

    data_for_option_char = fields.Function(fields.Char(
            'For Option',
            states={'invisible': True},
            on_change_with=['data_for_coverage'],
            depends=['data_for_coverage']),
        'on_change_with_data_for_option_char')

    @classmethod
    def default_the_kind(cls):
        if Transaction().context.get('kind', '') in ('data'):
            return 'data'
        else:
            return 'elem'

    @classmethod
    def default_elem_covered_data(cls, from_wizard=None):
        if Transaction().context.get('kind', '') in ('data', ''):
            return []
        if not from_wizard:
            from_wizard = CoveredDesc.get_context()
        contract = abstract.WithAbstract.get_abstract_objects(
            from_wizard, 'for_contract')
        covered_datas = []
        for option in contract.options:
            covered_data = cls()
            covered_data.the_kind = 'data'
            covered_data.init_from_option(option)
            covered_data.data_complementary_data = utils.init_complementary_data_from_ids(
                from_wizard.project.product.get_result(
                    'complementary_data_getter',
                    {
                        'date': covered_data.data_start_date,
                        'dd_args': {
                            'options': option.offered.code,
                            'kind': 'sub_elem',
                            'path': 'all'}})[0])
            covered_data.data_status = True
            covered_datas.append(covered_data)
        return abstract.WithAbstract.serialize_field(covered_datas)

    @staticmethod
    def get_coverages_model():
        res = utils.get_descendents(Coverage)
        res.append((Coverage.__name__, Coverage.__name__))
        return res

    def init_from_option(self, option):
        self.data_start_date = option.start_date
        self.option = option
        self.data_for_coverage = option.offered
        self.data_for_option_char = self.data_for_coverage.code
        self.data_coverage_name = self.data_for_coverage.get_rec_name('')

    def on_change_with_data_coverage_name(self):
        res = ''
        if self.data_for_coverage:
            res = self.data_for_coverage.get_rec_name('')
        return res

    def on_change_with_data_for_option_char(self):
        if not hasattr(self, 'data_for_coverage') and \
                self.data_for_coverage:
            return ''
        return utils.convert_ref_to_obj(self.data_for_coverage).code

    def get_currency(self):
        if self.data_covered_element():
            return self.data_covered_element.get_currency()


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
        contract = abstract.WithAbstract.get_abstract_objects(
            wizard, 'for_contract')
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


class SubscriptionProcessState(ProcessState, abstract.WithAbstract):
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
        contract = abstract.WithAbstract.get_abstract_objects(
            self, 'for_contract')
        Contract = Pool().get(contract.__name__)
        contract.finalize_contract()
        if not (hasattr(contract, 'billing_manager') and
                contract.billing_manager):
            bm = utils.instanciate_relation(contract, 'billing_manager')
            contract.billing_manager = [bm]
        for covered_element in contract.covered_elements:
            for covered_data in covered_element.covered_data:
                for option in contract.options:
                    if covered_data.coverage == option.offered:
                        covered_data.option = option
                        break
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
