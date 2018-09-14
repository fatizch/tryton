# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Commission',
    'CreateInvoicePrincipalAsk',
    ]


class Commission:
    __metaclass__ = PoolMeta
    __name__ = 'commission'

    @classmethod
    def _possible_notice_kinds(cls):
        return super(Commission, cls)._possible_notice_kinds() + ['benefits']

    @classmethod
    def _get_insurers_domain(cls, notice_kind):
        domain = super(Commission, cls)._get_insurers_domain(notice_kind)
        if notice_kind in ('all', 'benefits'):
            domain = ['OR', domain, [('benefits', '!=', None)]]
        return domain

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


class CreateInvoicePrincipalAsk:
    __metaclass__ = PoolMeta
    __name__ = 'commission.create_invoice_principal.ask'

    @classmethod
    def __setup__(cls):
        super(CreateInvoicePrincipalAsk, cls).__setup__()
        cls.notice_kind.selection.append(('benefits', 'Benefit'))
