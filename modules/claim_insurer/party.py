# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Insurer',
    ]


class Insurer:
    __metaclass__ = PoolMeta
    __name__ = 'insurer'

    @classmethod
    def _get_domain_from_notice_kind(cls, notice_kind):
        domain = super(Insurer, cls)._get_domain_from_notice_kind(notice_kind)
        if notice_kind in ('all', 'benefits'):
            domain = ['OR', domain, [('benefits', '!=', None)]]
        return domain

    def _get_slip_accounts(self, notice_kind):
        result = super(Insurer, self)._get_slip_accounts(notice_kind)
        if notice_kind not in ('all', 'benefits'):
            return result
        result |= {x.waiting_account for x in self.benefits
            if x.waiting_account}
        return result

    @classmethod
    def _get_slip_business_kind(cls, notice_kind):
        if notice_kind == 'benefits':
            return 'claim_insurer_invoice'
        return super(Insurer, cls)._get_slip_business_kind(notice_kind)
