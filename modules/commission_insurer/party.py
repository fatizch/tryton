# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond import backend


__all__ = [
    'Insurer',
    ]


class Insurer(metaclass=PoolMeta):
    __name__ = 'insurer'

    @classmethod
    def __register__(cls, module_name):
        super(Insurer, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        insurer_h = TableHandler(cls, module_name)
        # Migration from 1.10: Remove waiting_account on insurers
        if insurer_h.column_exist('waiting_account'):
            insurer_h.drop_column('waiting_account')

    def _get_slip_accounts(self, notice_kind):
        accounts = super()._get_slip_accounts(notice_kind)
        if notice_kind in ('options', 'all'):
            billing_accounts = {x.account_for_billing
                for x in self.options if x.account_for_billing}
            if billing_accounts:
                accounts |= set(billing_accounts)
        return accounts

    @classmethod
    def _get_slip_business_kind(cls, notice_kind):
        if notice_kind == 'options':
            return 'insurer_invoice'
        return super(Insurer, cls)._get_slip_business_kind(notice_kind)

    @classmethod
    def get_journal_from_notice_kind(cls, notice_kind):
        Journal = Pool().get('account.journal')
        if notice_kind in ('all', 'options'):
            journals = Journal.search([('type', '=', 'commission')])
            assert len(journals) == 1, 'Multiple commission journals or no ' \
                'commission journal defined'
            return journals[0]
        return super(Insurer, cls).get_journal_from_notice_kind(notice_kind)

    @classmethod
    def _get_domain_from_notice_kind(cls, notice_kind):
        base_domain = super(Insurer, cls)._get_domain_from_notice_kind(
            notice_kind)
        options_domain = [('options.account_for_billing', '!=', None)]
        if notice_kind == 'options':
            return options_domain
        elif notice_kind == 'all':
            return ['OR', options_domain, base_domain]
        return base_domain
