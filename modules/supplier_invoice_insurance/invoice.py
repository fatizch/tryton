from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    'InvoiceLine',
    ]

IS_IN_INVOICE_INSURANCE = Eval('business_kind') == 'in_invoice_insurance'


class Invoice:
    __name__ = 'account.invoice'

    insurer = fields.Many2One('insurer', 'Insurer', states={
            'invisible': ~IS_IN_INVOICE_INSURANCE,
            'required': IS_IN_INVOICE_INSURANCE,
            'readonly': Eval('state') != 'draft',
            },
        ondelete='RESTRICT',
        depends=['type', 'business_kind', 'state'])
    possible_related_contracts = fields.Function(
        fields.One2Many('contract', None, 'Possible Related Contracts',
            states={'invisible': True}),
        'on_change_with_possible_related_contracts')
    related_party = fields.Many2One('party.party', 'Related party', states={
            'invisible': ~IS_IN_INVOICE_INSURANCE,
            'required': IS_IN_INVOICE_INSURANCE,
            'readonly': Eval('state') != 'draft',
            }, domain=[('is_person', '=', True)], ondelete='RESTRICT',
        depends=['business_kind', 'state'])
    related_contract = fields.Many2One('contract', 'Related contract', states={
            'invisible': ~IS_IN_INVOICE_INSURANCE,
            'readonly': Eval('state') != 'draft',
            },
        domain=[('id', 'in', Eval('possible_related_contracts'))],
        ondelete='RESTRICT',
        depends=['business_kind', 'possible_related_contracts', 'state'])

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.business_kind.selection.append(
            ('in_invoice_insurance', 'Supplier Invoice Insurance'))
        cls.type.domain = ['AND',
            cls.type.domain,
            If(Eval('business_kind') == 'in_invoice_insurance',
                ('type', '=', 'in_invoice'),
                (),
                )]
        cls.type.depends += ['business_kind']
        cls.lines.domain = ['AND',
            cls.lines.domain,
            If(Eval('business_kind') == 'in_invoice_insurance',
                [('product.template.category.code', '=',
                    'in_invoice_insurance'),
                    ('type', '=', 'line')],
                [()],
                )]
        cls.lines.depends += ['business_kind']
        cls.account.domain = [
            If(Eval('business_kind') == 'in_invoice_insurance',
                [('company', '=', Eval('company', -1)),
                    ('kind', '=', 'receivable')],
                cls.account.domain,
                )]
        cls.account.depends += ['business_kind']

    @staticmethod
    def default_invoice_date():
        return utils.today()

    @fields.depends('related_party', 'related_contract',
        'possible_related_contracts')
    def on_change_related_party(self):
        if self.related_contract:
            if not self.related_party or (self.related_contract.id not in
                    self.possible_related_contracts):
                self.related_contract = None

    @fields.depends('related_party')
    def on_change_with_possible_related_contracts(self, name=None):
        if self.related_party:
            return [x.id for x in self.related_party.get_all_contracts()]
        return []

    @fields.depends('related_contract', 'insurer')
    def on_change_with_insurer(self):
        if not self.related_contract:
            return self.insurer.id if self.insurer else None
        insurers = list(set([x.coverage.insurer for x in
                    (self.related_contract.options
                        + self.related_contract.covered_element_options)]))
        if len(insurers) == 1:
            return insurers[0].id

    @fields.depends('business_kind')
    def on_change_party(self):
        super(Invoice, self).on_change_party()

    @fields.depends('business_kind')
    def on_change_type(self):
        super(Invoice, self).on_change_type()

    def __get_account_payment_term(self):
        if self.business_kind == 'in_invoice_insurance' and self.party:
            self.account = self.party.account_receivable
            if self.party.customer_payment_term:
                self.payment_term = self.party.customer_payment_term
            else:
                config = Pool().get('account.configuration')(1)
                self.payment_term = config.default_customer_payment_term
        else:
            super(Invoice, self).__get_account_payment_term()


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
