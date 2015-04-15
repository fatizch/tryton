from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Dunning',
    'Level',
    ]


class Dunning:
    __name__ = 'account.dunning'

    contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_line_field', searcher='search_line_field')


class Level:
    __name__ = 'account.dunning.level'

    contract_action = fields.Selection([
            ('', ''),
            ('terminate', 'Terminate Contract'),
            ('hold', 'Hold Contract')], 'Contract Action')
    termination_mode = fields.Selection([
            ('at_last_posted_invoice', 'At Last Posted Invoice'),
            ('at_last_paid_invoice', 'At Last Paid Invoice')],
            'Termination Mode', depends=['contract_action'],
            states={'invisible': Eval('contract_action') != 'terminate'})

    def process_hold_contracts(self, dunnings):
        pool = Pool()
        Contract = pool.get('contract')
        SubStatus = pool.get('contract.sub_status')
        hold_reason, = SubStatus.search([
                ('code', '=', 'unpaid_premium_hold')])
        contracts = set()
        for dunning in dunnings:
            if not dunning.contract:
                continue
            contracts.add(dunning.contract)
        if not contracts:
            return
        Contract.hold(list(contracts), hold_reason)

    def process_terminate_contracts(self, dunnings):
        pool = Pool()
        Contract = pool.get('contract')
        SubStatus = pool.get('contract.sub_status')
        to_terminate = defaultdict(list)
        termination_reason, = SubStatus.search([
                ('code', '=', 'unpaid_premium_termination')])
        for dunning in dunnings:
            if not dunning.contract:
                continue
            if self.termination_mode == 'at_last_posted_invoice':
                date = dunning.contract.last_posted_invoice_end
            elif self.termination_mode == 'at_last_paid_invoice':
                date = dunning.contract.last_paid_invoice_end
            to_terminate[date].append(dunning.contract)
        for date, contracts in to_terminate.iteritems():
            Contract.terminate(contracts, date, termination_reason)

    def process_dunnings(self, dunnings):
        if self.contract_action == 'terminate':
            self.process_terminate_contracts(dunnings)
        elif self.contract_action == 'hold':
            self.process_hold_contracts(dunnings)
        super(Level, self).process_dunnings(dunnings)

    @staticmethod
    def default_termination_mode():
        return 'at_last_posted_invoice'

    def test(self, line, date):
        res = super(Level, self).test(line, date)
        if not res:
            return res
        if line.contract and line.contract.current_dunning:
            # Do not generate a new dunning for an invoice on a contract
            # with a dunning in progress
            if line.contract.current_dunning.level.sequence > self.sequence:
                return False
        return res
