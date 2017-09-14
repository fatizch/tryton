# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, Button, StateView, StateTransition
from trytond.modules.coog_core import model, fields, coog_date

__all__ = [
    'FiscalYearSet',
    'FiscalYearSetWizard',
    ]


class FiscalYearSet(model.CoogView):
    'Fiscal Year Set'

    __name__ = 'fiscal_year.set'

    fiscal_year_sync_date = fields.Date('Fiscal Year Sync Date')
    fiscal_year_periods_frequency = fields.Selection([
            ('1', 'Monthly'),
            ('3', 'Quarterly'),
            ('6', 'Half Yearly'),
            ('12', 'Yearly'),
            ], 'Fiscal Year periods frequency')
    fiscal_year_periods_frequency_string = \
        fiscal_year_periods_frequency.translated(
            'fiscal_year_periods_frequency')
    fiscal_year_number = fields.Integer('Number of Fiscal Years to create')


class FiscalYearSetWizard(Wizard):
    'Fiscal Year Set Wizard'

    __name__ = 'fiscal_year.set.wizard'

    start_state = 'start'

    start = StateView('fiscal_year.set',
        'account_cog.fiscal_year_set_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Set', 'set_', 'tryton-ok', default=True),
            ])
    set_ = StateTransition()

    @classmethod
    def __setup__(cls):
        super(FiscalYearSetWizard, cls).__setup__()
        cls._error_messages.update({
                'fiscal_year': 'Fiscal Year',
                'post_move_sequence': 'Post Move Sequence',
                })

    def transition_set_(self):
        FiscalYear = Pool().get('account.fiscalyear')
        fiscal_years = []
        for i in range(0, self.start.fiscal_year_number):
            date = datetime.date(
                self.start.fiscal_year_sync_date.year + i,
                self.start.fiscal_year_sync_date.month,
                self.start.fiscal_year_sync_date.day)
            if FiscalYear.search([('start_date', '=', date)]):
                continue
            fiscal_years.append(self.new_fiscal_year(date))
        years = FiscalYear.create([x._save_values for x in fiscal_years])
        FiscalYear.create_period(years, int(
                self.start.fiscal_year_periods_frequency))
        return 'end'

    @classmethod
    def new_fiscal_year(cls, start_date):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Company = pool.get('company.company')
        company = Company(Transaction().context.get('company'))
        fiscal_year_str = cls.translate('fiscal_year')
        return FiscalYear(**{
                'start_date': start_date,
                'end_date': coog_date.add_day(
                    coog_date.add_year(start_date, 1), -1),
                'name': '%s %s' % (fiscal_year_str, start_date.year),
                'code': '%s_%s' % ('_'.join(fiscal_year_str.lower().split(' ')),
                   start_date.year),
                'company': company,
                'post_move_sequence': cls.create_sequence(start_date),
                })

    @classmethod
    def create_sequence(cls, start_date):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Company = pool.get('company.company')
        company = Company(Transaction().context.get('company'))

        sequence = Sequence(**{
                'company': company,
                'name': '%s - %s %s' % (
                    cls.translate('post_move_sequence'),
                    cls.translate('fiscal_year'), start_date.year),
                'code': 'account.move',
                'prefix': str(start_date.year),
                'padding': 9,
                })
        return Sequence.create([sequence._save_values])[0]

    @classmethod
    def translate(cls, s):
        return '%s' % cls.raise_user_error(s, raise_exception=False)
