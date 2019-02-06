# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = [
    'Insurer',
    ]


class Insurer(metaclass=PoolMeta):
    __name__ = 'insurer'

    @classmethod
    def _get_domain_from_notice_kind(cls, notice_kind):
        base_domain = super(Insurer, cls)._get_domain_from_notice_kind(
            notice_kind)
        benefits_domain = [('benefits', '!=', None)]
        if notice_kind == 'benefits':
            return benefits_domain
        elif notice_kind == 'all':
            return ['OR', benefits_domain, base_domain]
        return base_domain

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

    @classmethod
    def get_journal_from_notice_kind(cls, notice_kind):
        Journal = Pool().get('account.journal')
        if notice_kind == 'benefits':
            journals = Journal.search([('type', '=', 'claim_insurer_slip')])
            assert len(journals) == 1, 'Multiple claim insurer slip journals ' \
                'or no claim insurer slip journal defined'
            return journals[0]
        return super(Insurer, cls).get_journal_from_notice_kind(notice_kind)
