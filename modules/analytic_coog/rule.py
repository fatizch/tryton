# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import Unique

from trytond.modules.coog_core import export, fields

__all__ = [
    'Rule',
    ]


class Rule(export.ExportImportMixin):
    __metaclass__ = PoolMeta
    __name__ = 'analytic_account.rule'
    _func_key = 'code'

    code = fields.Char('Code', required=True)

    @classmethod
    def _export_light(cls):
        return super(Rule, cls)._export_light() | {'company', 'account',
            'party', 'journal'}

    @classmethod
    def __setup__(cls):
        super(Rule, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]
        cls._error_messages.update({
                'accounts_with_extra_details': 'You cannot create a rule using '
                'analytic accounts with type \'Distribution over extra '
                'details\':\n%(accounts)s'
                })

    @classmethod
    def validate(cls, rules):
        super(Rule, cls).validate(rules)
        distribution_over_details_accounts = [a.account
            for r in rules
            for a in r.analytic_accounts
            if a.account.type == 'distribution_over_extra_details']
        if distribution_over_details_accounts:
            cls.raise_user_error('accounts_with_extra_details',
                {'accounts': '\n'.join(
                    [a.rec_name for a in distribution_over_details_accounts])
                })
