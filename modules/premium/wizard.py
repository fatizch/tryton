# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.modules.coog_core import model, fields, utils

__all__ = [
    'DisplayContractPremium',
    'DisplayContractPremiumDisplayer',
    'DisplayContractPremiumDisplayerPremiumLine',
    ]


class DisplayContractPremium(Wizard):
    'Display Contrat Premium'

    __name__ = 'contract.premium.display'

    start_state = 'display'
    display = StateView('contract.premium.display.premiums',
        'premium.display_premiums_view_form', [
            # TODO: calculate price should be done in a separate transaction
            # in order to see the difference
            # Button('Calculate Prices', 'calculate_prices', 'tryton-refresh'),
            Button('Exit', 'end', 'tryton-cancel', default=True)])
    calculate_prices = StateTransition()

    @classmethod
    def __setup__(cls):
        super(DisplayContractPremium, cls).__setup__()
        cls._error_messages.update({
                'no_contract_found': 'No contract found in context',
                })

    @classmethod
    def get_children_fields(cls):
        return {
            'contract': ['options'],
            'contract.option': [],
            'options': [],
            }

    def new_line(self, name, line=None):
        return {
            'name': name,
            'premium': line.id if line else None,
            'premiums': [line.id] if line else [],
            'amount': line.amount if line else 0,
            'childs': [],
            }

    def add_lines(self, source, parent):
        for field_name in self.get_children_fields().get(source.__name__, ()):
            values = getattr(source, field_name, None)
            if not values:
                continue
            for elem in values:
                base_line = self.new_line(elem.rec_name)
                self.add_lines(elem, base_line)
                parent['childs'].append(base_line)
                parent['amount'] += base_line['amount']
        if source.premiums:
            for elem in source.premiums:
                name = ''
                if elem.rated_entity.rec_name == source.rec_name:
                    name = '%s - %s' % (elem.start, elem.end or '')
                else:
                    name = '%s (%s - %s)' % (elem.rated_entity.rec_name,
                        elem.start, elem.end or '')
                premium_line = self.new_line(name, elem)
                if elem.start <= utils.today() <= (
                        elem.end or datetime.date.max):
                    parent['amount'] += elem.amount
                parent['childs'].append(premium_line)
        return parent

    def default_display(self, name):
        try:
            contracts = Pool().get('contract').browse(
                Transaction().context.get('active_ids'))
        except:
            self.raise_user_error('no_contract_found')
        lines = []
        for contract in contracts:
            contract_line = self.new_line(contract.rec_name)
            self.add_lines(contract, contract_line)
            lines.append(contract_line)
        if len(lines) == 1:
            return {'premiums': lines}
        contracts_line = self.new_line('Total')
        contracts_line['amount'] = sum(line['amount']
            for line in lines)
        contracts_line['childs'] = lines
        return {'premiums': [contracts_line]}

    def transition_calculate_prices(self):
        Contract = Pool().get('contract')
        Contract.button_calculate_prices(Contract.browse(
                Transaction().context.get('active_ids', [])))
        return 'display'


class DisplayContractPremiumDisplayer(model.CoogView):
    'Display Contract Premium Displayer'

    __name__ = 'contract.premium.display.premiums'

    premiums = fields.One2Many('contract.premium.display.premiums.line',
        None, 'Premiums', readonly=True)


class DisplayContractPremiumDisplayerPremiumLine(model.CoogView):
    'Display Contract Premium Displayer Prmeium Line'

    __name__ = 'contract.premium.display.premiums.line'

    amount = fields.Numeric('Amount Today')
    childs = fields.One2Many('contract.premium.display.premiums.line', None,
        'Childs')
    premiums = fields.One2Many('contract.premium', None, 'Premium')
    premium = fields.Many2One('contract.premium', 'Premium')
    name = fields.Char('Name')
