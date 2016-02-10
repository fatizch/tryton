from trytond.pool import PoolMeta
from trytond.pyson import Eval, Not, And, Bool, If

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    'InvoiceLine',
    ]

IS_IN_INVOICE_ONLY = And((Eval('type') == 'in_invoice'), Eval(
    'business_type').in_([None, 'in_invoice']))


class Invoice:
    __name__ = 'account.invoice'

    insurer = fields.Many2One('insurer', 'Insurer', states={
            'invisible': Not(IS_IN_INVOICE_ONLY),
            'required': IS_IN_INVOICE_ONLY,
            },
        ondelete='RESTRICT',
        depends=['type', 'business_type'])
    possible_related_parties = fields.Function(
        fields.One2Many('party.party', None, 'Possible Related Parties',
            states={'invisible': True}),
        'on_change_with_possible_related_parties')
    possible_related_contracts = fields.Function(
        fields.One2Many('contract', None, 'Possible Related Contracts',
            states={'invisible': True}),
        'on_change_with_possible_related_contracts')
    related_party = fields.Many2One('party.party', 'Related party', states={
            'invisible': Not(IS_IN_INVOICE_ONLY),
            'required': IS_IN_INVOICE_ONLY,
            },
        domain=[
            If(Bool(Eval('possible_related_parties')),
                [('id', 'in', Eval('possible_related_parties')), ], [])],
        ondelete='RESTRICT',
        depends=['type', 'possible_related_parties'])
    related_contract = fields.Many2One('contract', 'Related contract', states={
            'invisible': Not(IS_IN_INVOICE_ONLY),
            },
        domain=[
            If(Bool(Eval('possible_related_contracts')),
                [('id', 'in', Eval('possible_related_contracts')), ], [])],
        ondelete='RESTRICT',
        depends=['type', 'possible_related_contracts'])

    @staticmethod
    def default_invoice_date():
        return utils.today()

    @fields.depends('related_contract', 'related_party')
    def on_change_related_contract(self):
        if self.related_party:
            if not self.related_contract or (self.related_party.id not in
                    self.on_change_with_possible_related_parties()):
                self.related_party = None

    @fields.depends('related_contract')
    def on_change_with_possible_related_parties(self, name=None):
        if self.related_contract:
            covered_parties = [x.party.id for x in
                self.related_contract.covered_elements]
            return covered_parties
        return []

    @fields.depends('related_party', 'related_contract')
    def on_change_related_party(self):
        if self.related_contract:
            if not self.related_party or (self.related_contract.id not in
                    self.on_change_with_possible_related_contracts()):
                self.related_contract = None

    @fields.depends('related_party')
    def on_change_with_possible_related_contracts(self, name=None):
        if self.related_party:
            return [x.id for x in self.related_party.get_all_contracts()]
        return []


class InvoiceLine:
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls._error_messages.update({
                'too_big_amount': ('Amount exceeds %s which is the maximum '
                    "allowed for product '%s'."),
                })

    @staticmethod
    def default_quantity():
        return 1

    def pre_validate(self):
        super(InvoiceLine, self).pre_validate()
        if self.product and self.product.capped_amount and (self.unit_price >
                self.product.capped_amount):
            self.raise_user_error('too_big_amount',
                (self.product.capped_amount, self.product.code))
