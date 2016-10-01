# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import model, fields
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond.transaction import Transaction
from trytond.pyson import Eval, PYSONEncoder


__metaclass__ = PoolMeta
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
    contract_parties = fields.Many2Many('party.party', None, None,
        'Contract Parties')
    covered_party = fields.Many2One('party.party', 'Covered Party',
        domain=[('id', 'in', Eval('contract_parties'))],
        depends=['contract_parties'])
    options = fields.Many2Many('contract.option', None, None, 'Options',
        domain=[('covered_element.party', '=', Eval('covered_party')),
                ('covered_element.contract', '=', Eval('contract'))],
        depends=['covered_party', 'contract'], required=True)

    @fields.depends('covered_party', 'options', 'contract')
    def on_change_covered_party(self):
        if not self.covered_party:
            self.options = []
            return
        self.options = [option for element in self.contract.covered_elements
            if element.party == self.covered_party
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
        parties = [x.party for x in contract.covered_elements if x.party]
        return {
            'contract': active_id,
            'end_date': None,
            'covered_party': parties[0].id if len(set(parties)) == 1 else None,
            'contract_parties': [x.id for x in parties]
            }

    def create_waiver(self, contract_id):
        pool = Pool()
        Waiver = pool.get('contract.waiver_premium')
        start_date = self.choice.start_date
        self.check_no_overlaps()
        waiver = Waiver(start_date=start_date, end_date=self.choice.end_date,
            contract=contract_id, options=[x for x in self.choice.options])
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
        to_reinvoice = ContractInvoice.search([('contract', '=', contract_id),
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
        Waiver = pool.get('contract.waiver_premium')
        waivers = list(self.choice.waivers)
        Waiver.write(waivers, {'end_date': self.choice.new_end_date})
        to_reinvoice = ContractInvoice.search([('contract', 'in',
                    [x.contract for x in waivers]),
                ('invoice.state', 'in', ['validated', 'posted', 'paid']),
                ('end', '>=', self.choice.waivers[0].start_date)])
        invoices = CreateWaiver._reinvoice(to_reinvoice)
        Contract.reconcile(list(set([x.contract for x in waivers])))
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [i.invoice.id for i in invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}
