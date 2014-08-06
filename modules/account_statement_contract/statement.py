from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval, If, Bool

__metaclass__ = PoolMeta

__all__ = [
    'Line',
    ]


class Line:
    __name__ = 'account.statement.line'

    contract = fields.Many2One('contract', 'Contract',
        domain=[
            If(Bool(Eval('party')), [('subscriber', '=', Eval('party'))], [])],
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
        changes = super(Line, self).on_change_invoice()
        changes['contract'] = (self.invoice.contract.id if self.invoice
            else None)
        return changes

    @fields.depends('party', 'contract')
    def on_change_party(self):
        changes = super(Line, self).on_change_party()
        if (self.party and self.contract
                and self.party != self.contract.subscriber):
            changes['contract'] = None
        return changes

    @fields.depends('contract', 'party', 'invoice')
    def on_change_contract(self):
        changes = {}
        if self.contract:
            if self.invoice:
                if self.invoice.contract != self.contract:
                    changes['invoice'] = None
            if self.party:
                if self.contract.subscriber != self.party:
                    changes['party'] = None
            else:
                changes['party'] = self.contract.subscriber.id
        return changes
