# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.i18n import gettext
from trytond.pool import Pool
from trytond.model.exceptions import ValidationError
from trytond.modules.coog_core import model, fields
from trytond.wizard import (Wizard, StateView, Button, StateAction)
from trytond.transaction import Transaction
from trytond.pyson import Eval, PYSONEncoder, If, Bool


class CreatePremiumModificationMixin:

    start_state = 'choice'
    choice = StateView('contract.premium_modification.create.choice',
        'contract_premium_modification.create_premium_modification_choice_view',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'reinvoice', 'tryton-ok', default=True),
            ])
    reinvoice = StateAction(
        'contract_insurance_invoice.act_premium_notice_form')

    def default_choice(self, name):
        pool = Pool()
        active_model = Transaction().context['active_model']
        active_id = Transaction().context['active_id']
        assert active_model == 'contract' and active_id
        contract = pool.get('contract')(active_id)
        return {
            'contract': active_id,
            'end_date': None,
            'covered_element': (
                contract.covered_elements[0].id
                if len(set(contract.covered_elements)) == 1 else None),
            'contract_covered_elements': [x.id
                for x in contract.covered_elements],
            'possible_discounts': [d.id for d in contract.possible_discounts],
            'modification_kind': self.modification_kind,
            }

    def create_modifications(self, contract_id):
        pool = Pool()
        WaiverPremium = pool.get('contract.waiver_premium')
        DiscountModification = pool.get(
            'contract.premium_modification.discount')
        self.check_no_overlaps()
        new_modifications = self.choice.contract.get_new_modifications(
            self.choice.options, self.choice.start_date, self.choice.end_date,
            modifications=[self.choice.discount])

        waivers, discounts = [], []
        if self.modification_kind == 'waiver':
            waivers = [m for m in new_modifications
                if isinstance(m, WaiverPremium)]
        elif self.modification_kind == 'discount':
            discounts = [m for m in new_modifications
                if isinstance(m, DiscountModification)]
        if waivers:
            WaiverPremium.save(waivers)
        if discounts:
            DiscountModification.save(discounts)

    @staticmethod
    def _reinvoice(to_reinvoice):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        invoices = ContractInvoice.reinvoice(to_reinvoice)
        return invoices

    def do_reinvoice(self, action):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        contract_id = Transaction().context['active_id']
        self.create_modifications(contract_id)
        # handle case where choice start date falls in the middle
        # of an invoicing period
        invoice_term_including_start = False
        for option in self.choice.options:
            for rule in option.coverage.premium_modification_rules:
                if rule.invoice_line_period_behaviour in [
                        'one_day_overlap', 'proportion']:
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
        self._reinvoice(to_reinvoice)
        Contract = pool.get('contract')
        Contract(contract_id).reconcile()
        contract_invoices = ContractInvoice.search([
                ('contract', '=', contract_id),
                ])
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [ci.invoice.id for ci in contract_invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}


class CreatePremiumModificationChoice(model.CoogView):
    'Create Premium Modification Choice'
    __name__ = 'contract.premium_modification.create.choice'

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
        domain=[If(Bool(Eval('covered_element')),
                [('covered_element', '=', Eval('covered_element'))],
                []),
            ('covered_element.contract', '=', Eval('contract'))],
        depends=['covered_element', 'contract'], required=True)
    discount = fields.Many2One('commercial_discount', "Discount",
        domain=[('id', 'in', Eval('possible_discounts', []))],
        states={
            'invisible': Eval('modification_kind') != 'discount',
            'required': Eval('modification_kind') == 'discount',
            },
        depends=['possible_discounts', 'modification_kind'])
    possible_discounts = fields.One2Many('commercial_discount', None,
        "Possible Discounts", readonly=True)
    modification_kind = fields.Selection([
            ('waiver', 'Waiver'),
            ('discount', 'Discount'),
            ], "Modification Kind", readonly=True)

    @fields.depends('covered_element', 'options', 'contract')
    def on_change_covered_element(self):
        if not self.covered_element:
            self.options = []
            return
        self.options = [option
            for element in self.contract.covered_elements
            if element == self.covered_element
            for option in element.options
            if option.coverage.premium_modification_rules]


class CreateWaivers(CreatePremiumModificationMixin, Wizard):
    'Create Waivers Wizard'
    __name__ = 'contract.premium_modification.create_waivers'
    modification_kind = 'waiver'

    def check_no_overlaps(self):
        pool = Pool()
        WaiverPremiumRule = pool.get('waiver_premium.rule')

        existing_modifications = set(m
            for option in self.choice.options
            for m in option.premium_modifications
            if isinstance(m.premium_modification.modification_rule,
                WaiverPremiumRule))
        if any(x.start_date <= self.choice.start_date <= (
                    x.end_date or datetime.date.max)
                for x in existing_modifications):
            raise ValidationError(gettext(
                    'contract_premium_modification.msg_waiver_overlaps'))


class CreateDiscounts(CreatePremiumModificationMixin, Wizard):
    'Create Discounts Wizard'
    __name__ = 'contract.premium_modification.create_discounts'
    modification_kind = 'discount'

    def check_no_overlaps(self):
        return


class SetPremiumModificationEndDateChoice(model.CoogView):
    'Create Premium Modification Choice'
    __name__ = 'contract.premium_modification.set_end_date.choice'

    modification_kind = fields.Selection([
            ('waiver', "Waiver"),
            ('discount', "Discount"),
            ], "Modification Kind")
    new_end_date = fields.Date('End Date')
    discounts = fields.Many2Many(
        'contract.premium_modification.discount', None, None,
        "Discounts On Premium", readonly=True,
        states={
            'invisible': Eval('modification_kind') != 'discount',
            },
        depends=['modification_kind'])
    waivers = fields.Many2Many(
        'contract.waiver_premium', None, None, 'Waivers Of Premium',
        readonly=True,
        states={
            'invisible': Eval('modification_kind') != 'waiver',
            },
        depends=['modification_kind'])


class SetPremiumModificationEndDate(Wizard):
    'Set Premium ModificationEnd Date'
    __name__ = 'contract.premium_modification.set_end_date'

    start_state = 'choice'
    choice = StateView('contract.premium_modification.set_end_date.choice',
        'contract_premium_modification.set_premium_mod_end_date_choice_view',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'reinvoice', 'tryton-ok'),
            ])
    reinvoice = StateAction(
        'contract_insurance_invoice.act_premium_notice_form')

    def default_choice(self, name):
        active_id = Transaction().context['active_id']
        model = Transaction().context['active_model']
        waivers, discounts = [], []
        if model == 'contract.waiver_premium':
            kind = 'waiver'
            waivers.append(active_id)
        elif model == 'contract.premium_modification.discount':
            kind = 'discount'
            discounts.append(active_id)
        return {
            'modification_kind': kind,
            'waivers': waivers,
            'discounts': discounts,
            'new_end_date': None,
            }

    def do_reinvoice(self, action):
        pool = Pool()
        CreateWaivers = pool.get(
            'contract.premium_modification.create_waivers', type='wizard')
        CreateDiscounts = pool.get(
            'contract.premium_modification.create_discounts', type='wizard')
        ContractInvoice = pool.get('contract.invoice')
        Contract = pool.get('contract')
        WaiverOption = pool.get('contract.waiver_premium-contract.option')
        DiscountOption = pool.get(
            'contract.premium_modification.discount-contract.option')

        modification_options = []
        if self.choice.modification_kind == 'waiver':
            premmods = self.choice.waivers
            PremModOption = WaiverOption
        elif self.choice.modification_kind == 'discount':
            premmods = self.choice.discounts
            PremModOption = DiscountOption

        for modification in premmods:
            modification_options += modification.premium_modification_options
        PremModOption.write(modification_options, {
                'end_date': self.choice.new_end_date,
                })
        to_reinvoice = ContractInvoice.search([
                ('contract', 'in',
                    [x.contract for x in premmods]),
                ('invoice.state', 'in', ['validated', 'posted', 'paid']),
                ('end', '>=', premmods[0].start_date),
                ])
        if self.choice.modification_kind == 'waiver':
            Wizard = CreateWaivers
        elif self.choice.modification_kind == 'discount':
            Wizard = CreateDiscounts
        Wizard._reinvoice(to_reinvoice)
        Contract.reconcile(list(set(x.contract for x in premmods)))
        contract_invoices = ContractInvoice.search([
                ('contract', 'in', [x.contract.id for x in premmods]),
                ])
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [ci.invoice.id for ci in contract_invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}
