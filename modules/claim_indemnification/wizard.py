# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction
from trytond.pyson import Eval, Equal

from trytond.modules.currency_cog.currency import DEF_CUR_DIG
from trytond.modules.cog_utils import fields, model, utils


__metaclass__ = PoolMeta
__all__ = [
    'CreateIndemnification',
    'IndemnificationCalculationResult',
    'IndemnificationDefinition',
    'ExtraDataValueDisplayer',
    'IndemnificationRegularisation',
    'ExtraDatasDisplayers',
    'FillExtraData',
    'IndemnificationValidateElement',
    'IndemnificationControlElement',
    'IndemnificationAssistantView',
    'IndemnificationAssistant',
    ]


class IndemnificationElement(model.CoopView):
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
    loss_date = fields.Date('Loss Date', readonly=True)
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
            'amount': indemnification.amount,
            'benefit': service.benefit.id,
            'contract': service.contract.id,
            'currency_digits': indemnification.currency_digits,
            'currency_symbol': indemnification.currency_symbol,
            'start_date': indemnification.start_date,
            'end_date': indemnification.end_date,
            'claim': service.loss.claim.id,
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


class IndemnificationAssistantView(model.CoopView):
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

    @classmethod
    def get_field_names(cls):
        return [
            ('', ''),
            ('amount', 'Montant'),
            ('start_date', 'Date de début'),
            ('end_date', 'Date de fin')]

    @fields.depends('control', 'field_sort', 'order_sort', 'mode', 'validate')
    def on_change_order_sort(self):
        self.on_change_field_sort()

    @fields.depends('control', 'field_sort', 'order_sort', 'mode', 'validate')
    def on_change_field_sort(self):
        pool = Pool()
        field = self.field_sort
        if not field:
            return
        if self.mode == 'validate':
            status_domain = ('status', 'in', ['controlled', 'cancelled'])
            model_name = 'claim.indemnification.assistant.validate.element'
        elif self.mode == 'control':
            status_domain = ('status', '=', 'validated')
            model_name = 'claim.indemnification.assistant.control.element'
        Element = pool.get(model_name)
        Indemnification = pool.get('claim.indemnification')
        results = Indemnification.search([status_domain],
            order=[(field, self.order_sort or 'ASC')])
        sorted_elements = []
        for result in results:
            sorted_elements.append(
                Element.from_indemnification(result))
        self.validate = sorted_elements

    @fields.depends('global_setter', 'validate', 'control')
    def on_change_global_setter(self):
        for element in self.validate:
            element.action = self.global_setter
        for element in self.control:
            element.action = self.global_setter


class IndemnificationAssistant(Wizard):
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
        pool = Pool()
        elements = []
        Indemnification = pool.get('claim.indemnification')
        Element = pool.get('claim.indemnification.assistant.validate.element')
        result = Indemnification.search([
                ('status', 'in', ['controlled', 'cancelled'])],
            order=[('amount', 'DESC')])
        for res in result:
            elements.append(
                Element.from_indemnification(res))
        return {
            'validate': elements, 'mode': 'validate',
            'global_setter': 'nothing', 'field_sort': 'amount',
            'order_sort': 'DESC'}

    def default_control_view_state(self, fields):
        pool = Pool()
        elements = []
        Indemnification = pool.get('claim.indemnification')
        Element = pool.get('claim.indemnification.assistant.control.element')
        result = Indemnification.search([
                ('status', '=', 'scheduled')],
            order=[('amount', 'DESC')])
        for res in result:
            elements.append(
                Element.from_indemnification(res))
        return {'control': elements, 'mode': 'control'}

    def transition_validation_state(self):
        pool = Pool()
        # Claim = pool.get('claim') # unused for the moment
        Note = pool.get('ir.note')
        Indemnification = pool.get('claim.indemnification')
        claims = []
        validate = []
        reject = []
        notes = []
        for element in self.validate_view_state.validate:
            if element.note:
                notes.append({
                        'message': element.note,
                        'resource': str(element.indemnification)})
            if element.action != 'nothing':
                if element.action == 'validate':
                    validate.append(element.indemnification.id)
                elif element.action == 'refuse':
                    reject.append(element.indemnification.id)
                claims.append(element.claim.id)
        Note.create(notes)
        Indemnification.validate_indemnification(
            Indemnification.browse(validate))
        Indemnification.invoice(Indemnification.browse(validate))
        Indemnification.reject_indemnification(
            Indemnification.browse(reject))
        return 'end'

    def transition_control_state(self):
        pool = Pool()
        Note = pool.get('ir.note')
        Indemnification = pool.get('claim.indemnification')
        notes = []
        validate = []
        reject = []
        for element in self.control_view_state.control:
            if element.note:
                notes.append({
                        'message': element.note,
                        'resource': str(element.indemnification)})
            if element.action != 'nothing':
                if element.action == 'validate':
                    validate.append(element.indemnification.id)
                elif element.action == 'refuse':
                    reject.append(element.indemnification.id)
        Note.create(notes)
        Indemnification.control_indemnification(
            Indemnification.browse(validate))
        Indemnification.reject_indemnification(
            Indemnification.browse(reject))
        return 'end'


class ExtraDataValueDisplayer(model.CoopView):
    'Extra Data Value Displayer'
    __name__ = 'claim.extra_data_value_displayer'

    name = fields.Char('Name')
    key = fields.Char('Key')
    value = fields.Numeric('Value')


class ExtraDatasDisplayers(model.CoopView):
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


class SelectService(model.CoopView):
    'Select Service'
    __name__ = 'claim.select_service'

    selected_service = fields.Many2One('claim.service', 'Selected Service',
        required=True,
        domain=([('id', 'in', Eval('possible_services'))]),
        depends=['possible_services'])
    possible_services = fields.One2Many('claim.service', None,
        'Possible Services', states={'invisible': True})


class IndemnificationDefinition(model.CoopView):
    'Indemnification Definition'
    __name__ = 'claim.indemnification_definition'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End_Date', required=True)
    extra_data = fields.Dict('extra_data', 'Extra Data')
    service = fields.Many2One('claim.service', 'Claim Service')
    beneficiary = fields.Many2One('party.party', 'Beneficiary')
    beneficiary_is_person = fields.Function(
        fields.Boolean('Beneficiary Is A Person', depends=['beneficiary']),
        'get_beneficiary_is_person')

    def get_beneficiary_is_person(self, name):
        if self.beneficiary:
            return self.beneficiary.is_person
        return False

    @fields.depends('beneficiary', 'beneficiary_is_person')
    def on_change_beneficiary(self):
        if self.beneficiary:
            self.beneficiary_is_person = self.beneficiary.is_person
        else:
            self.beneficiary_is_person = False

    def get_extra_data_values(self):
        return self.extra_data


class IndemnificationCalculationResult(model.CoopView):
    'Indemnification Calculation Result'
    __name__ = 'claim.indemnification_calculation_result'

    indemnification = fields.One2Many('claim.indemnification', None,
        'Indemnification')
    cancelled = fields.Many2Many(
        'claim.indemnification', None, None, 'Cancelled',
        states={'invisible': True})


class IndemnificationRegularisation(model.CoopView):
    'Indemnification Regularisation'
    __name__ = 'claim.indemnification_regularisation'

    amount = fields.Numeric('Regularisation Amount',
        digits=(16, 2), readonly=True)
    indemnification = fields.One2Many('claim.indemnification', None,
        'Indemnification')
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
            states={'invisible': ~Eval('payback_required')})
    payment_term_required = fields.Boolean('Payment Term Required',
        states={'invisible': True})
    payment_term = fields.Many2One(
        'account.invoice.payment_term', 'Payment Term',
        states={'invisible': ~Eval('payment_term_required')})

    @fields.depends('amount')
    def on_change_with_payback_required(self):
        return self.amount < 0

    @fields.depends('payback_method', 'payback_required')
    def on_change_with_payment_term_required(self):
        return (self.payback_required is True and
                    self.payback_method == 'planned')


class CreateIndemnification(Wizard):
    'Create Indemnification'
    __name__ = 'claim.create_indemnification'

    start_state = 'select_service_needed'
    select_service_needed = StateTransition()
    select_service = StateView('claim.select_service',
        'claim_indemnification.select_service_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'service_selected', 'tryton-go-next')])
    service_selected = StateTransition()
    definition = StateView('claim.indemnification_definition',
        'claim_indemnification.indemnification_definition_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Calculate', 'calculate', 'tryton-go-next')])
    calculate = StateTransition()
    result = StateView('claim.indemnification_calculation_result',
        'claim_indemnification.indemnification_calculation_result_view_form', [
            Button('Previous', 'definition', 'tryton-go-previous'),
            Button('Validate', 'regularisation', 'tryton-go-next')])
    regularisation = StateTransition()
    init_previous = StateTransition()
    select_regularisation = StateView('claim.indemnification_regularisation',
        'claim_indemnification.indemnification_regularisation_view_form', [
            Button('Previous', 'init_previous', 'tryton-go-previous'),
            Button('Valider', 'apply_regularisation', 'tryton-go-next')])
    apply_regularisation = StateTransition()

    def default_definition(self, name):
        pool = Pool()
        Service = pool.get('claim.service')
        Claim = pool.get('claim')
        Indemnification = pool.get('claim.indemnification')
        active_id = Transaction().context.get('active_id')
        if not active_id:
            return 'end'
        if Transaction().context.get('active_model') == 'claim.service':
            self.definition.service = Service(active_id)
            return 'definition'
        elif Transaction().context.get('active_model') == 'claim':
            claim = Claim(active_id)
            claim_services = [s for s in claim.delivered_services
                if not s.loss.end_date]
            if len(claim_services) == 1:
                self.definition.service = claim_services[0]
                return 'definition'
            self.select_service.possible_services = claim_services
            self.select_service.selected_services = claim_services[0]
            return 'select_service'
        elif (Transaction().context.get('active_model') ==
                'claim_indemnification'):
            indemnification = Indemnification(active_id)
            self.definition.start_date = indemnification.start_date
            self.definition.end_date = indemnification.end_date
            self.definition.service = indemnification.service
            self.result.indemnification = [indemnification]
            return 'result'
        else:
            return 'end'

    def transition_service_selected(self):
        self.definition.service = self.select_service.selected_service

    def delete_indemnification(self):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')
        if self.result and self.result.indemnification:
            Indemnification.delete(self.result.indemnification)

    def check_input(self):
        input_start_date = self.definition.start_date
        input_end_date = self.definition.end_date
        ClaimService = Pool().get('claim.service')
        service = self.definition.service
        if (input_end_date <= input_start_date or
                input_start_date <= service.loss.start_date):
            self.raise_user_error('wrong_date')
        return ClaimService.cancel_indemnification([service], input_start_date)

    def transition_calculate(self):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')
        ExtraData = pool.get('claim.service.extra_data')
        self.result.cancelled = self.check_input()
        indemnification = Indemnification(
            start_date=self.definition.start_date,
            end_date=self.definition.end_date
            )
        extra_data_values = self.definition.get_extra_data_values()
        extra_data = utils.get_value_at_date(
            self.definition.service.extra_datas, self.definition.start_date)
        if (extra_data.extra_data_values != extra_data_values):
            if (self.definition.start_date == extra_data.date or
                    self.definition.start_date ==
                    self.definition.service.loss.start_date and
                    not extra_data.date):
                extra_data.extra_data_values = extra_data_values
            else:
                extra_data = ExtraData(
                    extra_data_values=extra_data_values,
                    date=self.definition.start_date,
                    claim_service=self.definition.service)
            extra_data.save()
        self.definition.service.save()
        indemnification.init_from_service(self.definition.service)
        indemnification.beneficiary = self.definition.beneficiary
        Indemnification.calculate([indemnification])
        indemnification.save()
        self.result.indemnification = [indemnification]
        return 'result'

    def default_result(self, name):
        return {
            'indemnification': [x.id for x in self.result.indemnification],
            'cancelled': [x.id for x in self.result.cancelled],
            }

    def amount_available_for_regularisation(self):
        declared_res = self.result.indemnification[0].amount
        cancelled_res = 0
        for indemnification in self.result.cancelled:
            cancelled_res += indemnification.amount
        return declared_res - cancelled_res

    def transition_init_previous(self):
        self.result.indemnification = \
            self.select_regularisation.indemnification
        self.result.cancelled = self.select_regularisation.cancelled
        return 'result'

    def transition_regularisation(self):
        if self.result.cancelled:
            self.select_regularisation.indemnification = \
                [self.result.indemnification[0].id]
            self.select_regularisation.cancelled = self.result.cancelled
            return 'select_regularisation'
        return 'end'

    def default_select_regularisation(self, name):
        indemnification = self.select_regularisation.indemnification[0]
        amount = self.amount_available_for_regularisation()
        return {
            'amount': amount,
            'indemnification': [indemnification.id],
            'cancelled': [x.id for x in self.select_regularisation.cancelled]
            }

    def transition_apply_regularisation(self):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')
        indemnification = self.select_regularisation.indemnification[0]
        indemnification.save()
        cancelled = self.select_regularisation.cancelled
        payback_method = self.select_regularisation.payback_method
        payment_term = getattr(self.select_regularisation, 'payment_term', None)
        Indemnification.write(list(cancelled), {
                'payback_method': payback_method,
                'payment_term': payment_term.id if payment_term else None
                })
        return 'end'
