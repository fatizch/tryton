from trytond.pool import PoolMeta
from trytond.pyson import Eval, If, Bool
from trytond.modules.company import CompanyReport

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'Line',
    'BankDepositTicketReport',
    ]


class Line:
    __name__ = 'account.statement.line'

    contract = fields.Many2One('contract', 'Contract',
        domain=[('status', '!=', 'quote'),
            If(Bool(Eval('party')),
                [('subscriber', '=', Eval('party')), ], [])],
        depends=['party'])

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls.invoice.depends.append('contract')
        cls.invoice.domain.append(
            If(Bool(Eval('contract')), [('contract', '=', Eval('contract'))],
                []))

    @fields.depends('invoice', 'contract')
    def on_change_invoice(self):
        super(Line, self).on_change_invoice()
        self.contract = (self.invoice.contract if self.invoice else None)

    @fields.depends('statement', 'date')
    def on_change_statement(self):
        super(Line, self).on_change_statement()
        if self.statement and not self.date:
            self.date = self.statement.date

    @fields.depends('party', 'contract')
    def on_change_party(self):
        super(Line, self).on_change_party()
        if (self.party and self.contract
                and self.party != self.contract.subscriber):
            self.contract = None

    @fields.depends('contract', 'party', 'invoice')
    def on_change_contract(self):
        if self.contract:
            if self.invoice:
                if self.invoice.contract != self.contract:
                    self.invoice = None
            if self.party:
                if self.contract.subscriber != self.party:
                    self.party = None
            else:
                self.party = self.contract.subscriber

    def get_move_line(self):
        result = super(Line, self).get_move_line()
        contract = self.contract
        if not contract and self.invoice:
            contract = self.invoice.contract
        if not contract:
            return result
        result.contract = contract
        return result


class BankDepositTicketReport(CompanyReport):
    __name__ = 'account.statement.bank_deposit_ticket_report'
