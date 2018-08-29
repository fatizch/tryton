# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.model import Unique

from trytond.modules.coog_core import export, fields, coog_string

__all__ = [
    'Account',
    'AccountDistribution',
    'AnalyticAccountEntry',
    'MoveLine',
    ]


class Account(export.ExportImportMixin):
    __metaclass__ = PoolMeta
    __name__ = 'analytic_account.account'
    _func_key = 'code'

    pattern = fields.Many2One('extra_details.configuration',
        'Pattern', states={
            'invisible': Eval('type') != 'distribution_over_extra_details'},
        depends=['type'],
        domain=[('model_name', '=', str('analytic_account.line'))])

    @classmethod
    def _export_light(cls):
        return super(Account, cls)._export_light() | {'company', 'root',
            'parent'}

    @classmethod
    def __setup__(cls):
        super(Account, cls).__setup__()
        cls.type.selection.append(
            ('distribution_over_extra_details',
                'Distribution Over Extra Details'))
        cls.code.required = True
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    def distribute(self, amount):
        if self.type == 'distribution_over_extra_details':
            return self.distribute_over_extra_details(amount)
        else:
            return super(Account, self).distribute(amount)

    def distribute_over_extra_details(self, amount):
        assert self.type == 'distribution_over_extra_details'
        return [(self, amount, {})]


class AccountDistribution(export.ExportImportMixin):
    __metaclass__ = PoolMeta
    __name__ = 'analytic_account.account.distribution'
    _func_key = 'code'

    code = fields.Char('Code', required=True)

    @classmethod
    def _export_light(cls):
        return super(AccountDistribution, cls)._export_light() | {'parent',
            'account'}

    @classmethod
    def __setup__(cls):
        super(AccountDistribution, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)


class AnalyticAccountEntry:
    __metaclass__ = PoolMeta
    __name__ = 'analytic.account.entry'

    @classmethod
    def __setup__(cls):
        super(AnalyticAccountEntry, cls).__setup__()
        cls.account.domain = [
            ('root', '=', Eval('root')),
            ('type', 'in',
                ['normal', 'distribution', 'distribution_over_extra_details']),
            ]

    def get_analytic_lines(self, line, date):
        "Yield analytic lines for the accounting line and the date"
        pool = Pool()
        AnalyticLine = pool.get('analytic_account.line')
        if not self.account:
            return
        if self.account.type != 'distribution_over_extra_details':
            for al in super(AnalyticAccountEntry, self).get_analytic_lines(line,
                    date):
                yield al
        else:
            amount = line.debit or line.credit
            for account, amount, extra_details in \
                    self.account.distribute_over_extra_details(amount):
                analytic_line = AnalyticLine()
                if amount >= 0:
                    analytic_line.debit = amount if line.debit else Decimal(0)
                    analytic_line.credit = amount if line.credit else Decimal(0)
                else:
                    analytic_line.debit = -amount if line.credit else Decimal(0)
                    analytic_line.credit = -amount if line.debit else Decimal(0)
                analytic_line.account = account
                analytic_line.date = date
                analytic_line.extra_details = dict(extra_details)
                yield analytic_line


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    analytic_lines = fields.One2Many('analytic_account.line', 'move_line',
        'Analytic Lines')
