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
    'IndemnificationRegularization',
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
            status = 'controlled'
            model_name = 'claim.indemnification.assistant.validate.element'
        elif self.mode == 'control':
            status = 'scheduled'
            model_name = 'claim.indemnification.assistant.control.element'
        Element = pool.get(model_name)
        Indemnification = pool.get('claim.indemnification')
        results = Indemnification.search([
                ('status', '=', status)],
            order=[(field, self.order_sort)])
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
                ('status', '=', 'controlled')],
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


class IndemnificationRegularization(model.CoopView):
    'Indemnification Regularization'
    __name__ = 'claim.indemnification_regularization'

    amount_available_for_regularization = fields.Numeric(
        'Montant disponible pour regularisation',
        digits=(16, 2), readonly=True)
    amount_selected_for_regularisation = fields.Numeric(
        'Montant utilise pour regularisation',
        digits=(16, 2))
    indemnification = fields.One2Many('claim.indemnification', None,
        'Indemnification', states={'invisible': True})


class CreateIndemnification(Wizard):
    'Create Indemnification'
    __name__ = 'claim.create_indemnification'

    start_state = 'definition'
    definition = StateView('claim.indemnification_definition',
        'claim_indemnification.indemnification_definition_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Calculate', 'calculate', 'tryton-go-next')])
    calculate = StateTransition()
    result = StateView('claim.indemnification_calculation_result',
        'claim_indemnification.indemnification_calculation_result_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Validate', 'regularization', 'tryton-go-next')])
    regularization = StateTransition()
    select_regularization = StateView('claim.indemnification_regularization',
        'claim_indemnification.indemnification_regularization_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Valider', 'apply_regularization', 'tryton-go-next')])
    apply_regularization = StateTransition()

    def default_definition(self, name):
        pool = Pool()
        Service = pool.get('claim.service')
        service_id = Transaction().context.get('active_id')
        service = Service(service_id)
        non_cancelled = []
        for indemnification in service.indemnifications:
            if indemnification.status != 'cancelled':
                non_cancelled.append(indemnification)
        if non_cancelled:
            start_date = non_cancelled[-1].end_date + \
                relativedelta(days=1)
            beneficiary = non_cancelled[-1].beneficiary

        else:
            start_date = service.loss.start_date
            beneficiary = service.contract.get_policy_owner(
                service.loss.start_date)
        extra_data = utils.get_value_at_date(service.extra_datas, start_date)
        res = {
            'service': service_id,
            'start_date': start_date,
            'beneficiary': beneficiary.id,
            'end_date': service.loss.end_date
            if service.loss.end_date else None,
            'extra_data': extra_data.extra_data_values,
            }
        return res

    def transition_calculate(self):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')
        ExtraData = pool.get('claim.service.extra_data')
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
        self.indemnification = indemnification
        return 'result'

    def default_result(self, name):
        return {'indemnification': [self.indemnification.id]}

    def amount_available_for_regularization(self):
        res = 0
        for indemnification in self.definition.service.indemnifications:
            if indemnification.status == 'cancelled':
                res += indemnification.amount
            else:
                for detail in indemnification.details:
                    if detail.kind == 'regularization':
                        res += detail.amount
        return max(res, 0)

    def transition_regularization(self):
        if self.amount_available_for_regularization():
            self.indemnification = self.result.indemnification[0]
            return 'select_regularization'
        return 'end'

    def default_select_regularization(self, name):
        amount = min(self.amount_available_for_regularization(),
            self.indemnification.amount)
        return {
            'amount_available_for_regularization': amount,
            'amount_selected_for_regularisation': amount,
            'indemnification': [self.indemnification.id]
            }

    def transition_apply_regularization(self):
        pool = Pool()
        Detail = pool.get('claim.indemnification.detail')
        indemnification = self.select_regularization.indemnification[0]
        detail = Detail(
            indemnification=indemnification,
            kind='regularization',
            amount=-
            self.select_regularization.amount_selected_for_regularisation)
        detail.save()
        indemnification.amount -= \
            self.select_regularization.amount_selected_for_regularisation
        indemnification.save()
        return 'end'
