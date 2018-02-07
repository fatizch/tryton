# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Or, In
from trytond.modules.coog_core import fields

__all__ = [
    'Contract',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    dunning_status = fields.Function(
        fields.Char('Dunning Status', states={
                'invisible': Or(~Eval('dunning_status'),
                    In(Eval('status'), ['terminated', 'void']))},
            depends=['dunning_status']),
        'get_dunning_status', searcher='search_dunning_status')
    current_dunning = fields.Function(
        fields.Many2One('account.dunning', 'Current Dunning'),
        'get_current_dunning')

    def get_color(self, name):
        if self.dunning_status:
            return 'red'
        return super(Contract, self).get_color(name)

    @classmethod
    def search_dunning_status(cls, name, clause):
        pool = Pool()
        dunning = pool.get('account.dunning').__table__()
        contract = pool.get('contract').__table__()
        level = pool.get('account.dunning.level').__table__()
        line = pool.get('account.move.line').__table__()

        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        query = contract.join(line, condition=(
                (line.contract == contract.id) &
                (line.reconciliation == Null))
            ).join(dunning, condition=(
                (dunning.line == line.id) &
                (dunning.state == 'done'))
            ).join(level, condition=(
                dunning.level == level.id)
            ).select(contract.id,
                where=(Operator(level.name, value)))

        return [('id', 'in', query)]

    @classmethod
    def get_dunning_status(cls, contracts, name):
        pool = Pool()
        Dunning = pool.get('account.dunning')
        result = {contract.id: '' for contract in contracts}
        dunnings = Dunning.search([
                ('contract', 'in', [contract.id for contract in contracts]),
                ('state', '=', 'done'),
                ('active', '=', True)
                ])
        for dunning in dunnings:
            result[dunning.contract.id] = dunning.level.name
        return result

    @classmethod
    def get_current_dunning(cls, contracts, name):
        pool = Pool()
        Dunning = pool.get('account.dunning')
        result = {x.id: None for x in contracts}
        dunnings = Dunning.search([
                ('contract', 'in', [contract.id for contract in contracts]),
                ('active', '=', True)
                ])
        for dunning in dunnings:
            result[dunning.contract.id] = dunning.id
        return result

    def get_synthesis_rec_name(self, name=None):
        synthesis = super(Contract, self).get_synthesis_rec_name(name)
        if not self.dunning_status:
            return synthesis
        return synthesis + '(%s)' % self.dunning_status

    def get_icon(self, name=None):
        if self.dunning_status:
            return 'contract_red'
        return super(Contract, self).get_icon(name)

    def get_invoice_periods(self, up_to_date, from_date=None):
        if self.current_dunning:
            if self.current_dunning.level.contract_action == 'hold_invoicing':
                return []
        return super(Contract, self).get_invoice_periods(up_to_date, from_date)
