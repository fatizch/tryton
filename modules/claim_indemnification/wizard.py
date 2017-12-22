# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from dateutil.relativedelta import relativedelta

from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction
from trytond.pyson import Eval, Equal, Bool, Len, If

from trytond.modules.currency_cog.currency import DEF_CUR_DIG
from trytond.modules.coog_core import fields, model, utils, wizard_context
from trytond.modules.coog_core.coog_date import FREQUENCY_CONVERSION_TABLE


__all__ = [
    'CreateIndemnification',
    'IndemnificationCalculationResult',
    'IndemnificationDefinition',
    'ExtraDataValueDisplayer',
    'IndemnificationRegularisation',
    'ExtraDatasDisplayers',
    'FillExtraData',
    'SelectService',
    'IndemnificationValidateElement',
    'IndemnificationControlElement',
    'IndemnificationAssistantView',
    'IndemnificationAssistant',
    ]


class IndemnificationElement(model.CoogView):
    'Claim Indemnification Element'

    __name__ = 'claim.indemnification.assistant.element'

    action = fields.Selection([
            ('nothing', 'Do nothing'),
            ('validate', 'Validate'),
            ('refuse', 'Refuse')],
        'Action')
    start_date = fields.Date('Start Date', readonly=True)
    end_date = fields.Date('End Date', readonly=True)
    note = fields.Char('Extra Information', states={
            'required': Equal(Eval('action'), 'refuse')
            }, depends=['action'])
    currency_digits = fields.Integer(
        'Currency Digits', states={'invisible': True})
    amount = fields.Numeric(
        'Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'], readonly=True)
    currency_symbol = fields.Char('Currency Symbol')
    claim = fields.Many2One(
        'claim', 'Claim', readonly=True)
    indemnification = fields.Many2One(
        'claim.indemnification', 'Indemnification',
        states={'invisible': True, 'readonly': True})
    recipient = fields.Many2One(
        'party.party', 'Payment Recipient', readonly=True)
    loss_date = fields.Date('Loss Date', readonly=True)
    status = fields.Char('Status', readonly=True)
    benefit = fields.Many2One('benefit', 'Benefit', readonly=True)
    contract = fields.Many2One('contract', 'Contract', readonly=True)
    indemnification_details = fields.Many2Many(
        'claim.indemnification', '', None, 'Details',
        states={'readonly': True})

    @classmethod
    def from_indemnification(cls, indemnification):
        service = indemnification.service
        return {
            'action': 'nothing',
            'indemnification': indemnification.id,
            'indemnification.rec_name': indemnification.rec_name,
            'amount': indemnification.total_amount,
            'benefit': service.benefit.id,
            'benefit.rec_name': service.benefit.rec_name,
            'contract': service.contract.id,
            'contract.rec_name': service.contract.rec_name,
            'currency_digits': indemnification.currency_digits,
            'currency_symbol': indemnification.currency_symbol,
            'start_date': indemnification.start_date,
            'end_date': indemnification.end_date,
            'status': indemnification.status_string,
            'claim': service.loss.claim.id,
            'claim.rec_name': service.loss.claim.rec_name,
            'recipient': indemnification.beneficiary,
            'loss_date': service.loss.start_date,
            'indemnification_details': [indemnification.id]
            }


class IndemnificationValidateElement(IndemnificationElement):
    'Claim Indemnification Validate Element'

    __name__ = 'claim.indemnification.assistant.validate.element'


class IndemnificationControlElement(IndemnificationElement):
    'Claim Indemnification Control Element'

    __name__ = 'claim.indemnification.assistant.control.element'

    reason = fields.Char('Control Reason')

    @classmethod
    def from_indemnification(cls, indemnification):
        res = super(IndemnificationControlElement, cls).from_indemnification(
            indemnification)
        res['reason'] = indemnification.control_reason
        return res


class IndemnificationAssistantView(model.CoogView):
    'Indemnification Assistant View'

    __name__ = 'claim.indemnification.assistant.view'

    mode = fields.Char('View mode', states={'invisible': True})
    validate = fields.One2Many(
        'claim.indemnification.assistant.validate.element',
        '', 'Indemnifications to validate',
        states={'invisible': Equal(Eval('mode'), 'control')},
        depends=['mode'], delete_missing=True)
    control = fields.One2Many(
        'claim.indemnification.assistant.control.element',
        '', 'Indemnifications to control',
        states={'invisible': Equal(Eval('mode'), 'validate')},
        depends=['mode'], delete_missing=True)
    field_sort = fields.Selection('get_field_names', 'Sort By')
    order_sort = fields.Selection([
            ('ASC', 'Ascending'),
            ('DESC', 'Descending')],
        'Order By')
    global_setter = fields.Selection([
            ('nothing', 'Do Nothing'),
            ('validate', 'Validate'),
            ('refuse', 'Refuse')],
        'Global value')
    loss_kind = fields.Many2One('benefit.loss.description', 'Loss Kind')

    @classmethod
    def get_field_names(cls):
        return [
            ('', ''),
            ('total_amount', 'Montant'),
            ('start_date', 'Date de début'),
            ('end_date', 'Date de fin')]

    @fields.depends('control', 'field_sort', 'order_sort', 'mode', 'validate',
        'loss_kind')
    def on_change_order_sort(self):
        self.apply_filters()

    @fields.depends('control', 'field_sort', 'order_sort', 'mode', 'validate',
        'loss_kind')
    def on_change_field_sort(self):
        self.apply_filters()

    @fields.depends('control', 'field_sort', 'order_sort', 'mode', 'validate',
        'loss_kind')
    def on_change_loss_kind(self):
        self.apply_filters()

    def apply_filters(self):
        if self.mode == 'validate':
            domain = [('status', 'in', ['controlled', 'cancel_controlled',
                'validated', 'cancel_validated'])]
            model_name = 'claim.indemnification.assistant.validate.element'
        elif self.mode == 'control':
            domain = [('status', 'in', ['scheduled', 'cancel_scheduled'])]
            model_name = 'claim.indemnification.assistant.control.element'
        else:
            return
        pool = Pool()
        Element = pool.get(model_name)
        Indemnification = pool.get('claim.indemnification')
        if self.loss_kind:
            domain.append(('service.loss.loss_desc', '=', self.loss_kind.id))
        order = []
        if self.field_sort:
            order.append((self.field_sort, self.order_sort or 'ASC'))
        results = Indemnification.search(domain, order=order)
        sorted_elements = []
        for result in results:
            sorted_elements.append(
                Element.from_indemnification(result))
        if self.mode == 'control':
            self.control = sorted_elements
        elif self.mode == 'validate':
            self.validate = sorted_elements

    @fields.depends('global_setter', 'validate', 'control')
    def on_change_global_setter(self):
        for element in self.validate:
            element.action = self.global_setter
        for element in self.control:
            element.action = self.global_setter


class IndemnificationAssistant(Wizard, model.FunctionalErrorMixIn):
    'Indemnification Assistant'

    __name__ = 'claim.indemnification.assistant'

    start_state = 'init_state'
    init_state = StateTransition()
    validate_view_state = StateView(  # View and Selection
        'claim.indemnification.assistant.view',
        'claim_indemnification.indemnification_assistant_view_form',
        [
            Button('Quit', 'end', 'tryton-cancel'),
            Button('Done', 'validation_state', 'tryton-ok')])
    control_view_state = StateView(
        'claim.indemnification.assistant.view',
        'claim_indemnification.indemnification_assistant_view_form',
        [
            Button('Quit', 'end', 'tryton-cancel'),
            Button('Done', 'control_state', 'tryton-ok')])
    validation_state = StateTransition()
    control_state = StateTransition()

    @classmethod
    def __setup__(cls):
        super(IndemnificationAssistant, cls).__setup__()
        cls._error_messages.update({
            'cannot_refuse_cancel_indemnifications': "Cancelled "
            "indemnification %(indemnification)s can't be refused"})

    def transition_init_state(self):
        pool = Pool()
        # checks which entrypoint was called
        action_id = Transaction().context.get('action_id')
        action = pool.get('ir.action')(action_id)
        xml_id = action.xml_id.split('.')[1]
        if xml_id == 'indemnification_validate_wizard':
            return 'validate_view_state'
        elif xml_id == 'indemnification_control_wizard':
            return 'control_view_state'
        return 'end'

    def default_validate_view_state(self, fields):
        return {
            'validate': [], 'mode': 'validate',
            'global_setter': 'nothing', 'field_sort': 'total_amount',
            'order_sort': 'DESC'}

    def default_control_view_state(self, fields):
        return {'control': [], 'mode': 'control',
            'global_setter': 'nothing', 'field_sort': 'total_amount',
            'order_sort': 'DESC'}

    def check_validation_state(self):
        # can't refuse cancel indemnification
        for element in self.validate_view_state.validate:
            if (element.action == 'refuse' and
                    'cancel' in element.indemnification.status):
                self.append_functional_error(
                    'cannot_refuse_cancel_indemnifications',
                    {'indemnification': element.indemnification.rec_name})

    def check_control_state(self):
        # can't refuse cancel indemnification
        for element in self.control_view_state.control:
            if (element.action == 'refuse' and
                    'cancel' in element.indemnification.status):
                self.append_functional_error(
                    'cannot_refuse_cancel_indemnifications',
                    {'indemnification': element.indemnification.rec_name})

    def transition_validation_state(self):
        Indemnification = Pool().get('claim.indemnification')
        validate = []
        reject = {}
        with model.error_manager():
            self.check_validation_state()
        for element in self.validate_view_state.validate:
            if element.action != 'nothing':
                if element.action == 'validate':
                    validate.append(element.indemnification)
                elif element.action == 'refuse':
                    reject[element.indemnification] = {'note': element.note}
        Indemnification.validate_indemnification(validate)
        Indemnification.invoice(validate)
        Indemnification.reject_indemnification(reject)
        return 'end'

    def transition_control_state(self):
        pool = Pool()
        Note = pool.get('ir.note')
        Indemnification = pool.get('claim.indemnification')
        notes = []
        validate = []
        reject = {}
        with model.error_manager():
            self.check_control_state()
        for element in self.control_view_state.control:
            if element.note:
                notes.append({
                        'message': element.note,
                        'resource': str(element.indemnification)})
            if element.action != 'nothing':
                if element.action == 'validate':
                    validate.append(element.indemnification)
                elif element.action == 'refuse':
                    reject[element.indemnification] = {'note': element.note}
        Note.create(notes)
        Indemnification.control_indemnification(validate)
        Indemnification.reject_indemnification(reject)
        return 'end'


class ExtraDataValueDisplayer(model.CoogView):
    'Extra Data Value Displayer'
    __name__ = 'claim.extra_data_value_displayer'

    name = fields.Char('Name')
    key = fields.Char('Key')
    value = fields.Numeric('Value')


class ExtraDatasDisplayers(model.CoogView):
    'Extra Datas'
    __name__ = 'claim.extra_datas_displayers'

    date = fields.Date('Date', required=True)
    extra_data = fields.Dict('extra_data', 'Extra Data')
    service = fields.Many2One('claim.service', 'Claim Service')

    def get_extra_data_values(self):
        return self.extra_data


class FillExtraData(Wizard):
    'Define Extra Data'
    __name__ = 'claim.fill_extra_datas'

    start_state = 'definition'
    definition = StateView('claim.extra_datas_displayers',
        'claim_indemnification.extra_data_displayers_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Validate', 'create_extra_datas', 'tryton-go-next')])
    create_extra_datas = StateTransition()

    def default_definition(self, name):
        pool = Pool()
        Service = pool.get('claim.service')
        service_id = Transaction().context.get('active_id', None)
        service = Service(service_id)
        extra_data = utils.get_value_at_date(service.extra_datas,
            service.loss.start_date)
        res = {
            'service': service_id,
            'date': service.loss.start_date,
            'extra_data': extra_data.extra_data_values,
            }
        return res

    def transition_create_extra_datas(self):
        pool = Pool()
        ExtraData = pool.get('claim.service.extra_data')
        extra_data_values = self.definition.get_extra_data_values()
        extra_data = utils.get_value_at_date(
            self.definition.service.extra_datas, self.definition.date)
        if extra_data.extra_data_values != extra_data_values:
            if (self.definition.date == extra_data.date or
                    self.definition.date ==
                    self.definition.service.loss.start_date and
                    not extra_data.date):
                extra_data.extra_data_values = extra_data_values
            else:
                extra_data = ExtraData(
                    extra_data_values=extra_data_values,
                    date=self.definition.date,
                    claim_service=self.definition.service)
            extra_data.save()
        return 'end'


class SelectService(model.CoogView):
    'Select Service'
    __name__ = 'claim.select_service'

    selected_service = fields.Many2One('claim.service', 'Selected Service',
        required=True,
        domain=([('id', 'in', Eval('possible_services'))]),
        depends=['possible_services'])
    contract = fields.Many2One('contract', 'Contract', readonly=True)
    option = fields.Many2One('contract.option', 'Option', readonly=True)
    possible_services = fields.Many2Many('claim.service', None, None,
        'Possible Services', states={'invisible': True})

    @fields.depends('contract', 'option', 'selected_service')
    def on_change_selected_service(self):
        if self.selected_service:
            self.contract = self.selected_service.contract
            self.option = self.selected_service.option
        else:
            self.contract = None
            self.option = None


class IndemnificationDefinition(model.CoogView):
    'Indemnification Definition'
    __name__ = 'claim.indemnification_definition'

    indemnification_date = fields.Date('Indemnification Date',
        help='For capital indemnifications, the date at which the '
        'indemnification is expected to be paid', states={
            'invisible': Bool(Eval('is_period', False))},
        depends=['is_period'])
    start_date = fields.Date('Start Date', states={
            'invisible': ~Eval('is_period'),
            }, depends=['is_period'])
    end_date = fields.Date('End Date', states={
            'invisible': ~Eval('is_period'),
            }, depends=['is_period'])
    extra_data = fields.Dict('extra_data', 'Extra Data', states={
            'invisible': ~Eval('extra_data')})
    service = fields.Many2One('claim.service', 'Claim Service')
    is_period = fields.Boolean('Is Period')
    beneficiary = fields.Many2One('party.party', 'Beneficiary',
        help='The party to which the indemnification will be paid',
        domain=[If(Len(Eval('possible_beneficiaries', [])) == 0, [],
                [('id', 'in', Eval('possible_beneficiaries'))])],
        states={'readonly': Len(Eval('possible_beneficiaries', [])) == 1},
        depends=['possible_beneficiaries'],
        required=True)
    beneficiary_share = fields.Numeric('Beneficiary Share', readonly=True)
    possible_beneficiaries = fields.Many2Many('party.party', None, None,
        'Possible Beneficiaries', readonly=True)
    journal = fields.Many2One('account.payment.journal', 'Journal',
        required=True)
    product = fields.Many2One('product.product', 'Product', states={
            'invisible': Bool(Eval('product', False)) &
            (Len(Eval('possible_products', [])) == 1),
            }, required=True, domain=[('id', 'in', Eval('possible_products'))],
        depends=['possible_products'])
    possible_products = fields.Many2Many('product.product', None, None,
        'Possible Products')

    @fields.depends('beneficiary', 'beneficiary_share', 'is_period',
        'possible_beneficiaries', 'possible_products', 'product', 'start_date',
        'service', 'indemnification_date')
    def on_change_service(self):
        if not self.service:
            self.is_period = False
            self.beneficiary = None
            return
        else:
            benefit = self.service.benefit
            self.is_period = benefit.indemnification_kind != 'capital'
            beneficiary_data = self.service.get_beneficiaries_data(
                self.indemnification_date or self.start_date or utils.today())
            if not beneficiary_data:
                self.possible_beneficiaries = []
                self.beneficiary = None
            else:
                self.possible_beneficiaries = [x[0] for x in beneficiary_data]
                if len(beneficiary_data) == 1:
                    self.beneficiary = beneficiary_data[0][0]
                    self.beneficiary_share = beneficiary_data[0][1]
        self.update_product()

    @fields.depends('beneficiary', 'beneficiary_share', 'service',
        'start_date')
    def on_change_beneficiary(self):
        if not self.beneficiary or not self.service:
            return
        beneficiaries_data = self.service.get_beneficiaries_data(
            self.start_date or utils.today())
        if not beneficiaries_data:
            return
        for party, share in beneficiaries_data:
            if party == self.beneficiary:
                self.beneficiary_share = share
                return

    def get_possible_products(self, name):
        if not self.service:
            return []
        return [x.id for x in self.service.benefit.products]

    def update_product(self):
        Product = Pool().get('product.product')
        products = self.get_possible_products(None)
        if self.product and self.product.id not in products:
            self.product = None
        if len(products) == 1:
            self.product = Product(products[0])
        if products:
            self.possible_products = Product.browse(products)
        else:
            self.possible_products = []

    def get_extra_data_values(self):
        return self.extra_data


class IndemnificationCalculationResult(model.CoogView):
    'Indemnification Calculation Result'
    __name__ = 'claim.indemnification_calculation_result'

    indemnification = fields.One2Many('claim.indemnification', None,
        'Indemnification', readonly=True)

    @classmethod
    def view_attributes(cls):
        return super(IndemnificationCalculationResult, cls).view_attributes() \
            + [
                ("/form/group[@id='indemnification_request_group']/" +
                    "group[@id='warning_multiple']", 'states',
                    {'invisible': Len(Eval('indemnification', [])) <= 1}),
                ]


class IndemnificationRegularisation(model.CoogView):
    'Indemnification Regularisation'
    __name__ = 'claim.indemnification_regularisation'

    remaining_amount = fields.Numeric('Remaining Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        readonly=True)
    cancelled_amount = fields.Numeric('Cancelled Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        readonly=True)
    new_indemnification_amount = fields.Numeric('New Indemnification Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        readonly=True)
    indemnification = fields.One2Many('claim.indemnification', None,
        'Indemnification', readonly=True)
    cancelled = fields.Many2Many(
        'claim.indemnification', None, None, 'Cancelled', readonly=True)
    payback_required = fields.Boolean('Payback Required',
        states={'invisible': True})
    payback_method = fields.Selection([
            ('continuous', 'Continuous'),
            ('immediate', 'Immediate'),
            ('planned', 'Planned'),
            ('', ''),
            ], 'Payback Method',
        states={'invisible': ~Eval('payback_required'),
            'required': Bool(Eval('payback_required'))},
        depends=['payback_required'])
    payment_term_required = fields.Boolean('Payment Term Required',
        states={'invisible': True})
    payment_term = fields.Many2One(
        'account.invoice.payment_term', 'Payment Term',
        states={'invisible': ~Eval('payment_term_required'),
                'required': Bool(Eval('payment_term_required'))},
        depends=['payment_term_required'])
    currency_digits = fields.Integer(
        'Currency Digits', states={'invisible': True})

    @fields.depends('remaining_amount')
    def on_change_with_payback_required(self):
        return self.remaining_amount < 0

    @fields.depends('payback_method', 'payback_required')
    def on_change_with_payment_term_required(self):
        return (self.payback_required is True and
            self.payback_method == 'planned')


class CreateIndemnification(wizard_context.PersistentContextWizard):
    'Create Indemnification'
    __name__ = 'claim.create_indemnification'

    start_state = 'select_service_needed'
    select_service_needed = StateTransition()
    select_service = StateView('claim.select_service',
        'claim_indemnification.select_service_view_form', [
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Continue', 'service_selected', 'tryton-go-next',
                default=True)])
    service_selected = StateTransition()
    definition = StateView('claim.indemnification_definition',
        'claim_indemnification.indemnification_definition_view_form', [
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Possible Services', 'select_service', 'tryton-go-previous'),
            Button('Calculate', 'calculate', 'tryton-go-next', default=True)])
    calculate = StateTransition()
    cancel = StateTransition()
    result = StateView('claim.indemnification_calculation_result',
        'claim_indemnification.indemnification_calculation_result_view_form', [
            Button('Previous', 'definition', 'tryton-go-previous'),
            Button('Validate', 'regularisation', 'tryton-go-next',
                default=True)])
    regularisation = StateTransition()
    init_previous = StateTransition()
    select_regularisation = StateView('claim.indemnification_regularisation',
        'claim_indemnification.indemnification_regularisation_view_form', [
            Button('Previous', 'init_previous', 'tryton-go-previous'),
            Button('Valider', 'apply_regularisation', 'tryton-go-next',
                default=True)])
    apply_regularisation = StateTransition()

    @classmethod
    def __setup__(cls):
        super(CreateIndemnification, cls).__setup__()
        cls._error_messages.update({
                'wrong_date': 'End date must be greater than the start date',
                'end_date_future': 'Indemnifications in '
                'the future are not allowed',
                'end_date_exceeds_loss': 'The end date must not exceed '
                'the loss end date',
                'end_date_required': 'End date is required',
                'start_date_required': 'Start date is required',
                })

    def possible_services(self, claim):
        res = []
        for delivered in claim.delivered_services:
            if delivered.can_be_indemnified is False:
                continue
            if not delivered.loss.end_date or not delivered.indemnifications:
                res.append(delivered)
                continue
            sorted_indemnifications = sorted([x
                    for x in delivered.indemnifications
                    if x.status != 'cancelled'],
                key=lambda x: x.start_date)
            if sorted_indemnifications[-1].end_date < delivered.loss.end_date:
                res.append(delivered)
                continue
            for idx, indemn in enumerate(sorted_indemnifications):
                if idx + 1 == len(sorted_indemnifications):
                    break
                if (sorted_indemnifications[idx + 1].start_date >
                        indemn.end_date + relativedelta(days=1)):
                    res.append(delivered)
                    break
        return res

    def transition_select_service_needed(self):
        pool = Pool()
        Service = pool.get('claim.service')
        Indemnification = pool.get('claim.indemnification')
        Claim = pool.get('claim')
        active_id = Transaction().context.get('active_id')
        if not active_id:
            return 'end'
        if Transaction().context.get('active_model') == 'claim.service':
            self.definition.service = Service(active_id)
            return 'definition'
        elif Transaction().context.get('active_model') == 'claim':
            possible_services = self.possible_services(Claim(active_id))
            if len(possible_services) == 1:
                self.definition.service = possible_services[0]
                return 'definition'
            return 'select_service'
        elif (Transaction().context.get('active_model') ==
                'claim.indemnification'):
            indemnification = Indemnification(active_id)
            self.definition.start_date = indemnification.start_date
            self.definition.indemnification_date = indemnification.start_date
            self.definition.end_date = indemnification.end_date
            self.definition.service = indemnification.service
            self.definition.beneficiary = indemnification.beneficiary
            self.definition.product = indemnification.product
            self.result.indemnification = [indemnification]
            return 'result'
        else:
            return 'end'

    def default_select_service(self, name):
        pool = Pool()
        Claim = pool.get('claim')
        if not Transaction().context.get('active_model') == 'claim':
            return {}
        claim = Claim(Transaction().context.get('active_id'))
        possible_services = self.possible_services(claim)
        return {
            'possible_services': [s.id for s in possible_services],
            'selected_service': possible_services[0].id
            if len(possible_services) == 1 else None,
            }

    def _reset_indemnifications(self):
        if 'indemnifications' in self.wizard_context:
            indemnifications = self.wizard_context['indemnifications']
            if indemnifications:
                Pool().get('claim.indemnification').delete(indemnifications)
            self.wizard_context.pop('indemnifications')
        if hasattr(self, 'result') and self.result and getattr(
                self.result, 'indemnification', None):
            self.result.indemnification = []

    def transition_service_selected(self):
        self.definition.service = self.select_service.selected_service
        self._reset_indemnifications()
        return 'definition'

    def transition_cancel(self):
        self._reset_indemnifications()
        return 'end'

    def get_end_date(self, start_date, service):
        if service.loss.end_date:
            return service.loss.end_date
        elif service.annuity_frequency:
            nb_month = FREQUENCY_CONVERSION_TABLE[service.annuity_frequency]
            period_start_date = start_date + relativedelta(day=1,
                month=((start_date.month - 1) // nb_month) * nb_month + 1)
            return period_start_date + relativedelta(months=nb_month, days=-1)
        return None

    def get_cancelled_indemnification(self, service):
        return [i for i in service.indemnifications if i.status == 'cancelled']

    def default_definition(self, name):
        result = getattr(self, 'result', None)
        configuration = Pool().get('claim.configuration').get_singleton()
        if self.result and getattr(result, 'indemnification', None):
            service = self.result.indemnification[0].service
            beneficiary = self.result.indemnification[0].beneficiary
            start_date = self.result.indemnification[0].start_date
            end_date = self.result.indemnification[-1].end_date
            product_id = self.result.indemnification[0].product.id
            share = self.result.indemnification[0].share
        else:
            share = 1
            product_id = None
            definition = getattr(self, 'definition', None)
            if definition and hasattr(definition, 'service'):
                service = definition.service
            elif configuration:
                return {'journal': configuration.payment_journal.id}
            else:
                return {}
            non_cancelled = []
            for indemnification in service.indemnifications:
                if 'cancel' not in indemnification.status:
                    non_cancelled.append(indemnification)
            if non_cancelled and non_cancelled[-1].end_date:
                start_date = non_cancelled[-1].end_date + \
                    relativedelta(days=1)
                beneficiary = non_cancelled[-1].beneficiary
                product_id = non_cancelled[-1].product.id
            else:
                start_date = service.loss.start_date
                beneficiary = None
            end_date = self.get_end_date(start_date, service)
            if service.benefit.indemnification_kind == 'capital':
                start_date = utils.today()
                end_date = None
        extra_data = utils.get_value_at_date(service.extra_datas,
            start_date).extra_data_values
        # Update initial extra_data with the current version if necessary
        new_data = service.benefit.get_extra_data_def(service)
        for k, v in new_data.items():
            if k not in extra_data:
                extra_data[k] = v
        if end_date and start_date > end_date:
            start_date = None
            end_date = None
        return {
            'service': service.id,
            'start_date': start_date,
            'indemnification_date': start_date,
            'end_date': end_date,
            'beneficiary': beneficiary.id if beneficiary else None,
            'extra_data': extra_data,
            'product': product_id,
            'beneficiary_share': share,
            'journal': configuration.payment_journal.id,
            }

    def check_input(self):
        if self.definition.is_period:
            input_start_date = self.definition.start_date
        else:
            input_start_date = self.definition.indemnification_date
        input_end_date = self.definition.end_date
        service = self.definition.service
        if self.definition.is_period:
            if not input_start_date:
                self.raise_user_error('start_date_required')
            if not input_end_date:
                self.raise_user_error('end_date_required')
        if (input_end_date and
                input_end_date > utils.today()):
            self.raise_user_error('end_date_future')
        if (input_end_date and service.loss.end_date and
                input_end_date > service.loss.end_date):
            self.raise_user_error('end_date_exceeds_loss')
        if input_end_date and input_start_date and (
                input_end_date < input_start_date or
                input_start_date < service.loss.start_date):
            self.raise_user_error('wrong_date')

    def update_service_extra_data(self, values):
        service = self.definition.service
        if self.definition.is_period:
            input_start_date = self.definition.start_date
        else:
            input_start_date = self.definition.indemnification_date
        service.update_extra_data(input_start_date or
            service.loss.start_date, values)
        service.save()

    def init_indemnifications(self):
        Indemnification = Pool().get('claim.indemnification')
        indemnifications = getattr(self.result, 'indemnification', None)
        if not indemnifications:
            indemnifications = [
                Indemnification(service=self.definition.service)]
        for indemnification in indemnifications:
            self.update_indemnification(indemnification)
        return indemnifications

    def update_indemnification(self, indemnification):
        if self.definition.is_period:
            input_start_date = self.definition.start_date
        else:
            input_start_date = self.definition.indemnification_date
        indemnification.start_date = input_start_date
        indemnification.end_date = self.definition.end_date
        indemnification.journal = self.definition.journal
        indemnification.amount = 0
        indemnification.total_amount = 0
        indemnification.currency = indemnification.service.get_currency()
        indemnification.currency_digits = indemnification.currency.digits
        indemnification.beneficiary = self.definition.beneficiary
        indemnification.share = self.definition.beneficiary_share
        indemnification.init_from_service(indemnification.service)
        indemnification.product = self.definition.product

    def clear_indemnifications(self):
        ClaimService = Pool().get('claim.service')
        if self.definition.is_period:
            input_start_date = self.definition.start_date
        else:
            input_start_date = self.definition.indemnification_date
        ClaimService.cancel_indemnification([self.definition.service],
            input_start_date, self.definition.end_date,
            beneficiary=self.definition.beneficiary)
        indemnifications = getattr(self.result, 'indemnification', None)
        if not indemnifications:
            return
        self.result.indemnification = [x.id
            for x in Pool().get('claim.indemnification').search([
                    ('id', 'in', [x.id for x in indemnifications])])]

    def transition_calculate(self):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')
        self.check_input()
        self.clear_indemnifications()
        self.update_service_extra_data(self.definition.get_extra_data_values())
        indemnifications = self.init_indemnifications()
        Indemnification.calculate(indemnifications)
        self.result.indemnification = indemnifications
        return 'result'

    def default_result(self, name):
        self.wizard_context['indemnifications'] = list(
            self.result.indemnification)
        return {
            'indemnification': [x.id for x in self.result.indemnification],
            }

    def transition_init_previous(self):
        self.result.indemnification = \
            self.select_regularisation.indemnification
        self.result.cancelled = self.select_regularisation.cancelled
        return 'result'

    def transition_regularisation(self):
        if self.result.indemnification:
            Pool().get('claim.indemnification').save(
                self.result.indemnification)
        cancelled = self.get_cancelled_indemnification(
            self.result.indemnification[0].service)
        if cancelled:
            self.select_regularisation.indemnification = \
                [self.result.indemnification[0].id]
            self.select_regularisation.cancelled = cancelled
            return 'select_regularisation'
        return 'end'

    def default_select_regularisation(self, name):
        indemnification = self.select_regularisation.indemnification[0]
        new_indemnification_amount = \
            self.result.indemnification[0].total_amount
        cancelled_amount = 0
        for cur_indemn in self.get_cancelled_indemnification(
                self.result.indemnification[0].service):
            cancelled_amount += cur_indemn.total_amount
        remaining_amount = new_indemnification_amount - cancelled_amount
        return {
            'remaining_amount': remaining_amount,
            'new_indemnification_amount': new_indemnification_amount,
            'cancelled_amount': cancelled_amount,
            'indemnification': [indemnification.id],
            'cancelled': [x.id for x in self.select_regularisation.cancelled],
            'currency_digits': indemnification.currency_digits
            }

    def transition_apply_regularisation(self):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')
        indemnification = self.select_regularisation.indemnification[0]
        indemnification.save()
        cancelled = self.select_regularisation.cancelled
        payback_method = self.select_regularisation.payback_method
        payment_term = getattr(self.select_regularisation, 'payment_term',
            None)
        Indemnification.write(list(cancelled), {
                'payback_method': payback_method,
                'payment_term': payment_term.id if payment_term else None
                })
        return 'end'
