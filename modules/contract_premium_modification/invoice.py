# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.modules.coog_core import fields

__all__ = [
    'Invoice',
    'InvoiceLineDetail',
    ]


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def _can_post_invoice(cls, invoice):
        res = super(Invoice, cls)._can_post_invoice(invoice)
        contract = invoice.contract
        if (res or not contract or
                not contract.product._must_invoice_after_contract):
            return res

        # We must allow invoices to go further than the contract end date if
        # the product "_must_invoice_after_contract" on termination
        if (contract.status == 'terminated' and
                invoice.start and invoice.start <= contract.final_end_date
                and invoice.start >= contract.initial_start_date
                and invoice.end and invoice.end > contract.final_end_date):
            return True
        return res


class InvoiceLineDetail(metaclass=PoolMeta):
    __name__ = 'account.invoice.line.detail'

    waiver = fields.Many2One('contract.waiver_premium', "Waiver of Premium",
        select=True, ondelete='RESTRICT', readonly=True)
    discount = fields.Many2One('contract.premium_modification.discount',
        "Discount on Premium", select=True, ondelete='RESTRICT', readonly=True)

    @property
    def premium_modification(self):
        if self.waiver:
            return self.waiver
        if self.discount:
            return self.discount
        return None

    @premium_modification.setter
    def premium_modification(self, value):
        pool = Pool()
        Waiver = pool.get('contract.waiver_premium')
        Discount = pool.get('contract.premium_modification.discount')

        if isinstance(value, Waiver):
            self.discount = None
            self.waiver = value
        elif isinstance(value, Discount):
            self.discount = value
            self.waiver = None
        else:
            self.discount = None
            self.waiver = None

    @classmethod
    def get_possible_parent_field(cls):
        return super().get_possible_parent_field() | {'waiver', 'discount'}
