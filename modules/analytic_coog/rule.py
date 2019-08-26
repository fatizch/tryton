# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta
from trytond.model import Unique
from trytond.model.exceptions import ValidationError

from trytond.modules.coog_core import export, fields

__all__ = [
    'Rule',
    ]


class Rule(export.ExportImportMixin, metaclass=PoolMeta):
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
            ('code_uniq', Unique(t, t.code), 'analytic_coog.msg_code_unique'),
            ]

    @classmethod
    def validate(cls, rules):
        super(Rule, cls).validate(rules)
        distribution_over_details_accounts = [a.account
            for r in rules
            for a in r.analytic_accounts
            if a.account.type == 'distribution_over_extra_details']
        if distribution_over_details_accounts:
            raise ValidationError(gettext(
                    'analytic_coog.msg_accounts_with_extra_details',
                    accounts='\n'.join(
                        a.rec_name for a in distribution_over_details_accounts)
                    ))
