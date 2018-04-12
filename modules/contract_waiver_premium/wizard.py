# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import Pool
from trytond.modules.coog_core import model, fields
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond.transaction import Transaction
from trytond.pyson import Eval, PYSONEncoder


__all__ = [
    'CreateWaiverChoice',
    'CreateWaiver',
    'SetWaiverEndDateChoice',
    'SetWaiverEndDate',
    ]


class CreateWaiverChoice(model.CoogView):
    'Create Waiver Choice'
    __name__ = 'contract.waiver_premium.create.choice'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    contract = fields.Many2One('contract', 'Contract', required=True)
    contract_covered_elements = fields.Many2Many('contract.covered_element',
        None, None, 'Contract Covered Elements')
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element',
        domain=[('id', 'in', Eval('contract_covered_elements'))],
        depends=['contract_covered_elements'])
    options = fields.Many2Many('contract.option', None, None, 'Options',
        domain=[('covered_element', '=', Eval('covered_element')),
                ('covered_element.contract', '=', Eval('contract'))],
        depends=['covered_element', 'contract'], required=True)

    @fields.depends('covered_element', 'options', 'contract')
    def on_change_covered_element(self):
        if not self.covered_element:
            self.options = []
            return
        self.options = [option for element in self.contract.covered_elements
            if element == self.covered_element
            for option in element.options if option.with_waiver_of_premium]


class CreateWaiver(Wizard):
    'Create Waiver Wizard'
    __name__ = 'contract.waiver_premium.create'

    start_state = 'choice'
    choice = StateView('contract.waiver_premium.create.choice',
        'contract_waiver_premium.create_waiver_choice_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'reinvoice', 'tryton-ok', default=True)])
    reinvoice = StateAction(
        'contract_insurance_invoice.act_premium_notice_form')

    @classmethod
    def __setup__(cls):
        super(CreateWaiver, cls).__setup__()
        cls._error_messages.update({
                'waiver_overlaps':
                'You are trying to create overlapping waivers',
                })

    def default_choice(self, name):
        pool = Pool()
        active_model = Transaction().context['active_model']
        active_id = Transaction().context['active_id']
        assert active_model == 'contract' and active_id
        contract = pool.get('contract')(active_id)
        return {
            'contract': active_id,
            'end_date': None,
            'covered_element': contract.covered_elements[0].id
            if len(set(contract.covered_elements)) == 1 else None,
            'contract_covered_elements': [x.id
                for x in contract.covered_elements]
            }

    def create_waiver(self, contract_id):
        pool = Pool()
        Waiver = pool.get('contract.waiver_premium')
        WaiverOption = pool.get('contract.waiver_premium-contract.option')
        start_date = self.choice.start_date
        self.check_no_overlaps()
        waiver_options = []
        for option in self.choice.options:
            waiver_options.append(WaiverOption(start_date=start_date,
                    end_date=self.choice.end_date, option=option))
        waiver = Waiver(contract=contract_id, waiver_options=waiver_options)
        waiver.save()

    def check_no_overlaps(self):
        existing_waivers = set([x for option in self.choice.options
                for x in option.waivers])
        if any([x.start_date <= self.choice.start_date <= (x.end_date
                        or datetime.date.max) for x in existing_waivers]):
            self.raise_user_error('waiver_overlaps')

    @staticmethod
    def _reinvoice(to_reinvoice):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        Invoice = pool.get('account.invoice')
        invoices = ContractInvoice.reinvoice(to_reinvoice)
        Invoice.post([x.invoice for x in invoices])
        return invoices

    def do_reinvoice(self, action):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        contract_id = Transaction().context['active_id']
        self.create_waiver(contract_id)
        # handle case where choice start date falls in the middle
        # of an invoicing period
        invoice_term_including_start = False
        for option in self.choice.options:
            if option.coverage.waiver_premium_rule:
                behaviour = option.coverage.waiver_premium_rule[0]. \
                    invoice_line_period_behaviour
                if behaviour in ['one_day_overlap', 'proportion']:
                    invoice_term_including_start = True
                    break
        if invoice_term_including_start:
            to_reinvoice = ContractInvoice.search([
                    ('contract', '=', contract_id),
                    ('invoice.state', 'in', ['validated', 'posted', 'paid']),
                    ('end', '>=', self.choice.start_date),
                    ('start', '<=', self.choice.end_date or datetime.date.max)])
        else:
            to_reinvoice = ContractInvoice.search([
                    ('contract', '=', contract_id),
                    ('invoice.state', 'in', ['validated', 'posted', 'paid']),
                    ('start', '>=', self.choice.start_date),
                    ('start', '<=', self.choice.end_date or datetime.date.max)])
        invoices = self._reinvoice(to_reinvoice)
        Contract = pool.get('contract')
        Contract(contract_id).reconcile()
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [i.invoice.id for i in invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}


class SetWaiverEndDateChoice(model.CoogView):
    'Create Waiver Choice'
    __name__ = 'contract.waiver_premium.set_end_date.choice'

    new_end_date = fields.Date('End Date')
    waivers = fields.Many2Many('contract.waiver_premium', None, None, 'Waiver',
        readonly=True)


class SetWaiverEndDate(Wizard):
    'Set Waiver End Date'
    __name__ = 'contract.waiver_premium.set_end_date'

    start_state = 'choice'
    choice = StateView('contract.waiver_premium.set_end_date.choice',
        'contract_waiver_premium.set_waiver_end_date_choice_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'reinvoice', 'tryton-ok')])
    reinvoice = StateAction(
        'contract_insurance_invoice.act_premium_notice_form')

    def default_choice(self, name):
        active_id = Transaction().context['active_id']
        return {
            'waivers': [active_id],
            'new_end_date': None,
            }

    def do_reinvoice(self, action):
        pool = Pool()
        CreateWaiver = pool.get('contract.waiver_premium.create',
            type='wizard')
        ContractInvoice = pool.get('contract.invoice')
        Contract = pool.get('contract')
        WaiverOption = pool.get('contract.waiver_premium-contract.option')
        waiver_options = []
        for waiver in self.choice.waivers:
            waiver_options += waiver.waiver_options
        WaiverOption.write(waiver_options, {
                'end_date': self.choice.new_end_date})
        to_reinvoice = ContractInvoice.search([('contract', 'in',
                    [x.contract for x in self.choice.waivers]),
                ('invoice.state', 'in', ['validated', 'posted', 'paid']),
                ('end', '>=', self.choice.waivers[0].start_date)])
        invoices = CreateWaiver._reinvoice(to_reinvoice)
        Contract.reconcile(list(set([x.contract for x in self.choice.waivers])))
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [i.invoice.id for i in invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}
