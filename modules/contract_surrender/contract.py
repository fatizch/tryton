# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.server_context import ServerContext

from trytond.modules.coog_core import model, fields, utils

__all__ = [
    'Contract',
    'Option',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    can_surrender = fields.Function(
        fields.Boolean('Can surrender'),
        'getter_can_surrender')
    surrender_invoice = fields.Function(
        fields.Many2One('account.invoice', 'Surrender invoice',
            help='The surrender invoice for the contract'),
        'getter_surrender_invoice')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_surrender': {
                    'readonly': ~Eval('can_surrender', False)},
                })
        cls._error_messages.update({
                'will_surrender': 'Contracts will be surrendered',
                'cannot_surrender': 'Contract %(contract)s cannot be '
                'surrendered',
                'no_surrenderable_options': 'No options were found that can '
                'be surrendered for contract %(contract)s',
                'surrender_invoice_description': 'Surrender of %(contract)s',
                'auto_surrendering': 'Contracts will automatically be '
                'surrendered',
                })

    @classmethod
    def getter_can_surrender(cls, contracts, name):
        result = {}
        for contract in contracts:
            if contract.status in ('void', 'quote', 'terminated'):
                result[contract.id] = False
            elif all(not x.surrender_rules
                    for x in contract.product.coverages):
                result[contract.id] = False
            else:
                result[contract.id] = not contract.surrender_invoice
        return result

    @classmethod
    def getter_surrender_invoice(cls, contracts, name):
        Invoice = Pool().get('account.invoice')
        result = {x.id: None for x in contracts}
        for invoice in Invoice.search([
                    ('contract', 'in', [x.id for x in contracts]),
                    ('state', 'in', ('posted', 'paid')),
                    ('business_kind', '=', 'surrender')]):
            result[invoice.contract.id] = invoice.id
        return result

    @classmethod
    @model.CoogView.button_action('contract_surrender.act_surrender_contract')
    def button_surrender(cls, contracts):
        pass

    @classmethod
    def surrender(cls, contracts, surrender_date):
        SubStatus = Pool().get('contract.sub_status')
        surrender_reason = SubStatus.get_sub_status('surrendered')
        cls.do_surrender(contracts, surrender_date)
        cls.terminate(contracts, surrender_date, surrender_reason)

    @classmethod
    def do_surrender(cls, contracts, surrender_date):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        Event = pool.get('event')
        cls.raise_user_warning('will_surrender_%s' % str([x.id for x in
                    contracts[:10]]), 'will_surrender')
        with model.error_manager():
            cls.check_for_surrender(contracts, surrender_date)
        contract_invoices = cls.generate_surrender_invoices(contracts,
            surrender_date)
        if contract_invoices:
            Invoice.save([x.invoice for x in contract_invoices])
            ContractInvoice.save(contract_invoices)
            Invoice.post([x.invoice for x in contract_invoices])
        Event.notify_events(contracts, 'surrender_contract')

    @classmethod
    def check_for_surrender(cls, contracts, surrender_date):
        for contract in contracts:
            if not contract.can_surrender:
                contract.append_functional_error('cannot_surrender',
                    {'contract': contract.rec_name})
                continue
            options = [x for x in (contract.options +
                    contract.covered_element_options)
                if x.surrender_allowed(surrender_date)]
            if not options:
                contract.append_functional_error(
                    'no_surrenderable_options', {
                        'contract': contract.rec_name})

    @classmethod
    def generate_surrender_invoices(cls, contracts, surrender_date):
        contract_invoices = []
        for contract in contracts:
            contract_invoice = contract.init_surrender_invoice(surrender_date)
            invoice = contract_invoice.invoice
            lines = []
            for option, surrender_amount in contract.calculate_surrenders(
                    surrender_date):
                lines.append(option.new_surrender_line(surrender_amount))
            invoice.lines = lines
            contract_invoices.append(contract_invoice)
        cls.finalize_surrender_invoices(contracts, contract_invoices)
        return contract_invoices

    def init_surrender_invoice(self, surrender_date):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        config = pool.get('account.configuration').get_singleton()
        lang = self.company.party.lang
        if not lang:
            self.company.raise_user_error('missing_lang',
                {'party': self.company.rec_name})
        invoice = Invoice(
            invoice_address=self.get_contract_address(utils.today()),
            contract=self,
            company=self.company,
            type='in',
            business_kind='surrender',
            journal=config.surrender_journal,
            party=self.subscriber,
            currency=self.currency,
            account=self.subscriber.account_payable,
            payment_term=config.surrender_payment_term,
            state='validated',
            invoice_date=max(utils.today(), surrender_date),
            accounting_date=None,
            description=self._surrender_invoice_description(surrender_date),
            )
        contract_invoice = ContractInvoice()
        contract_invoice.contract = self
        contract_invoice.invoice = invoice
        contract_invoice.non_periodic = True
        return contract_invoice

    def _surrender_invoice_description(self, surrender_date):
        return self.raise_user_error('surrender_invoice_description',
            {'contract': self.rec_name}, raise_exception=False)

    def calculate_surrenders(self, surrender_date):
        surrenders = []
        options = [x for x in (self.options + self.covered_element_options)
            if x.surrender_allowed(surrender_date)]
        for option in options:
            surrenders.append(
                (option, option.calculate_surrender(surrender_date)))
        return surrenders

    @classmethod
    def finalize_surrender_invoices(cls, contracts, contract_invoices):
        pass

    @classmethod
    def terminate(cls, contracts, at_date, termination_reason):
        to_surrender, to_terminate = [], []
        for contract in contracts:
            if contract.auto_surrender(at_date):
                to_surrender.append(contract)
            else:
                to_terminate.append(contract)
        if to_surrender:
            # Surrendering will also terminate the contracts
            cls.raise_user_warning('auto_surrendering_%s' % ','.join(
                    [str(x.id) for x in to_surrender]), 'auto_surrendering')
            Contract.surrender(to_surrender, at_date)
        if to_terminate:
            super(Contract, cls).terminate(to_terminate, at_date,
                termination_reason)

    def auto_surrender(self, at_date):
        with model.error_manager():
            self.check_for_surrender([self], at_date)
            manager = ServerContext().get('error_manager')
            result = not manager.has_errors
            manager.clear_errors()
        return result


class Option:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option'

    @classmethod
    def __setup__(cls):
        super(Option, cls).__setup__()
        cls._error_messages.update({
                'surrender_line_description': 'Surrender of %(option)s',
                })

    def surrender_allowed(self, surrender_date):
        if not self.parent_contract.can_surrender:
            return False
        if not self.is_active_at_date(surrender_date):
            return False
        if not self.coverage.surrender_rules:
            return False
        surrender_rule = self.coverage.surrender_rules[0]
        if surrender_rule.eligibility_rule:
            data_dict = {}
            data_dict['date'] = surrender_date
            self.init_dict_for_rule_engine(data_dict)
            result = surrender_rule.calculate_eligibility_rule(
                data_dict, return_full=True)
            if result.errors:
                for error in result.print_errors():
                    self.append_functional_error(error)
            if result.warnings:
                self.raise_user_warning(str(('surrender', self.id)),
                    '\r\r'.join(result.print_warnings()))
            return result.result
        return True

    def calculate_surrender(self, surrender_date):
        data_dict = {}
        data_dict['date'] = surrender_date
        self.init_dict_for_rule_engine(data_dict)
        surrender_rule = self.coverage.surrender_rules[0]
        return surrender_rule.calculate_rule(data_dict)

    def new_surrender_line(self, amount):
        line = Pool().get('account.invoice.line')()
        line.type = 'line'
        line.unit_price = self.currency.round(amount)
        line.quantity = 1
        line.unit = None
        line.account = self.coverage.surrender_rules[0].surrender_account
        line.details = []
        line.description = self._surrender_line_description()
        return line

    def _surrender_line_description(self):
        return self.raise_user_error('surrender_line_description',
            {'option': self.rec_name}, raise_exception=False)
