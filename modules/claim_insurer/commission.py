# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Commission',
    'CreateInvoicePrincipal',
    'CreateInvoicePrincipalAsk',
    ]


class Commission:
    __metaclass__ = PoolMeta
    __name__ = 'commission'

    @classmethod
    def get_insurer_invoice_type(cls, notice_kind):
        if notice_kind == 'benefits':
            return 'out'
        return super(Commission, cls).get_insurer_invoice_type(notice_kind)

    @classmethod
    def get_insurer_business_kind(cls, notice_kind):
        if notice_kind == 'benefits':
            return 'claim_insurer_invoice'
        return super(Commission, cls).get_insurer_business_kind(notice_kind)

    @classmethod
    def retrieve_commissions(cls, invoices, until_date, insurers, notice_kind):
        if notice_kind == 'benefits':
            # There is no commission in case of benefit insurer notice
            return []
        return super(Commission, cls).retrieve_commissions(invoices,
            until_date, insurers, notice_kind)


class CreateInvoicePrincipal:
    __metaclass__ = PoolMeta
    __name__ = 'commission.create_invoice_principal'

    def get_insurers(self):
        if self.ask.notice_kind == 'benefits':
            Insurer = Pool().get('insurer')
            insurers = Insurer.search([('party', 'in', self.ask.insurers)])
            insurers_with_accounts = Insurer.get_insurers_waiting_accounts(
                insurers, 'benefits')
            return list({x[0] for x in insurers_with_accounts})
        return super(CreateInvoicePrincipal, self).get_insurers()


class CreateInvoicePrincipalAsk:
    __metaclass__ = PoolMeta
    __name__ = 'commission.create_invoice_principal.ask'

    @classmethod
    def __setup__(cls):
        super(CreateInvoicePrincipalAsk, cls).__setup__()
        cls.notice_kind.selection.append(('benefits', 'Benefit'))

    @fields.depends('notice_kind', 'description')
    def on_change_with_description(self, name=None):
        if self.notice_kind == 'benefits':
            Invoice = Pool().get('account.invoice')
            return Invoice.raise_user_error('batch_claims_paid',
                raise_exception=False)
        return super(
            CreateInvoicePrincipalAsk, self).on_change_with_description(name)
