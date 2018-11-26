# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond import backend

from trytond.modules.coog_core import fields


__all__ = [
    'Insurer',
    ]


class Insurer(metaclass=PoolMeta):
    __name__ = 'insurer'

    group_insurer_invoices = fields.Boolean('Group Insurer Invoices',
        help='If True, all insurer related invoices (premiums / claims / etc) '
        'will be grouped in one')

    @classmethod
    def __register__(cls, module_name):
        super(Insurer, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        insurer_h = TableHandler(cls, module_name)
        # Migration from 1.10: Remove waiting_account on insurers
        if insurer_h.column_exist('waiting_account'):
            insurer_h.drop_column('waiting_account')

    @classmethod
    def __setup__(cls):
        super(Insurer, cls).__setup__()
        cls._error_messages.update({
                'mixed_insurer_configuration': 'You cannot generate invoices '
                'simultaneously for insurers whose group invoice '
                'configuration is different',
                'bad_insurer_configuration': 'Notice kind does not match '
                'insurer configuration',
                })

    @classmethod
    def generate_slip_parameters(cls, notice_kind, parties=None):
        insurers = cls._get_insurers_from_notice_kind(notice_kind, parties)
        return [x._generate_slip_parameter(notice_kind) for x in insurers]

    @classmethod
    def _get_insurers_from_notice_kind(cls, notice_kind, parties):
        domain = cls._get_domain_from_notice_kind(notice_kind)
        if parties:
            domain = [domain, [('party', 'in', parties)]]
        else:
            if notice_kind == 'all':
                domain = [domain, [('group_insurer_invoices', '=', True)]]
            else:
                domain = [domain, [
                        ('group_insurer_invoices', 'in', (False, None))]]
        insurers = cls.search(domain)
        if not insurers:
            return []
        grouped = {bool(x.group_insurer_invoices) for x in insurers}
        if len(grouped) != 1:
            cls.raise_user_error('mixed_insurer_configuration')
        if bool(grouped.pop()) != (notice_kind == 'all'):
            cls.raise_user_error('bad_insurer_configuration')
        return insurers

    @classmethod
    def _get_domain_from_notice_kind(cls, notice_kind):
        if notice_kind in ('options', 'all'):
            return [('options.account_for_billing', '!=', None)]
        return []

    def _generate_slip_parameter(self, notice_kind):
        accounts = self._get_slip_accounts(notice_kind)
        return {
            'insurer': self,
            'party': self.party,
            'accounts': list(accounts),
            'slip_kind': self._get_slip_business_kind(notice_kind),
            }

    def _get_slip_accounts(self, notice_kind):
        if notice_kind in ('options', 'all'):
            billing_accounts = {x.account_for_billing
                for x in self.options if x.account_for_billing}
            if billing_accounts:
                return set(billing_accounts)
        return set()

    @classmethod
    def _get_slip_business_kind(cls, notice_kind):
        if notice_kind == 'all':
            return 'all_insurer_invoices'
        elif notice_kind == 'options':
            return 'insurer_invoice'
