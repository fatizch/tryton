# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from itertools import groupby
from sql import Table, Column

from trytond.pool import Pool

from trytond.modules.migrator import migrator
from trytond.modules.migrator import tools

__all__ = [
    'MigratorLoan',
    'MigratorLoanIncrement',
]


class MigratorLoanIncrement(migrator.Migrator):
    """Migrator loan increment"""

    __name__ = 'migrator.loan.increment'

    @classmethod
    def __setup__(cls):
        super(MigratorLoanIncrement, cls).__setup__()

        cls.table = Table('loan_increment')
        cls.model = 'loan.increment'
        cls.func_key = 'loan'
        cls.columns = {k: k for k in ('loan', 'number', 'start_date',
            'begin_balance', 'number_of_payments', 'payment_amount', 'rate',
            'payment_frequency')}
        cls.cache_obj = {'loan': {}}
        cls.error_messages.update({
                'zero_payments': 'zero_payments for loan increment #%s',
                })

    @classmethod
    def query_data(cls, numbers):
        select = super(MigratorLoanIncrement, cls).query_data(numbers)
        select.where = ((Column(cls.table, cls.columns['loan']).in_(numbers))
            & (Column(cls.table, cls.columns['number_of_payments']) > 0))
        select.order_by = (Column(cls.table, cls.columns['number']))
        return select

    @classmethod
    def init_cache(cls, rows):
        super(MigratorLoanIncrement, cls).init_cache(rows)
        cls.cache_obj['loan'] = tools.cache_from_query('loan', ('number', ),
            ('number', [r['loan'] for r in rows]))

    @classmethod
    def populate(cls, row):
        Loan = Pool().get('loan')
        row = super(MigratorLoanIncrement, cls).populate(row)
        row['manual'] = True
        if not row['number_of_payments']:
            cls.logger.error(cls.error_message('zero_payments') % (
                row[cls.func_key], row['number']))
        row['number'] = None
        cls.resolve_key(row, 'loan', 'loan')
        row['loan'] = Loan(row['loan'])
        return row

    @classmethod
    def migrate_rows(cls, rows_all, ids):
        pool = Pool()
        Loan = pool.get('loan')
        LoanIncrement = pool.get('loan.increment')
        increments = defaultdict(list)
        for loan_number, _rows in groupby(rows_all, key=lambda r: r['loan']):
            rows = list(_rows)
            for (idx, row) in enumerate(rows):
                row = cls.populate(cls.sanitize(row))
                if idx == 0:
                    increments[loan_number].extend(rows[0]['loan'].increments)
                    number_increments = len(increments[loan_number])
                if row['loan'].first_payment_date > row['start_date']:
                    cls.logger.debug('Adjust loan %s increment start date' %
                        row['loan'].number)
                    row['start_date'] = row['loan'].first_payment_date
                del row['loan']
                increment = LoanIncrement(**row)
                increment.number = number_increments + idx + 1
                increments[loan_number].append(increment)
                increments[loan_number] = Loan.insert_manual_increment(
                    increment, increments[loan_number])
        return increments


class MigratorLoan(migrator.Migrator):
    """Migrator loan"""

    __name__ = 'migrator.loan'

    @classmethod
    def __setup__(cls):
        super(MigratorLoan, cls).__setup__()
        cls.table = Table('loan')
        cls.model = 'loan'
        cls.func_key = 'number'
        cls.columns = {k: k for k in ('number', 'external_number', 'kind',
            'payment_frequency', 'amount', 'duration', 'funds_release_date',
            'first_payment_date', 'rate', 'deferral', 'deferral_duration',
            'lender')}
        cls.transcoding = {'kind': {}, 'payment_frequency': {},
            'deferral': {}, 'duration_unit': {}}
        cls.error_messages.update({
                'unknown_kind': "unknown loan kind '%s'",
                'unknown_payment_frequency':
                "unknown loan payment frequency: '%s'",
                'unknown_deferral': "unknown loan deferral: '%s'",
                'non_zero_rate': ("non zero rate '%s' forbidden for "
                    'interest-free loan'),
                'zero_rate': 'zero rate forbidden for loan',
                'existing_loan': 'loan already exists with that number',
                'mandatory_field': "missing mandatory field '%s'",
                })

    @classmethod
    def init_cache(cls, rows):
        super(MigratorLoan, cls).init_cache(rows)
        cls.currency = Pool().get('currency.currency').search(
            [('code', '=', 'EUR')])[0]
        cls.company = Pool().get('company.company').search([])[0]
        cls.cache_obj['loan'] = tools.cache_from_query('loan', ('number', ),
            ('number', [r['number'] for r in rows]))

    @classmethod
    def populate(cls, row):
        row = super(MigratorLoan, cls).populate(row)
        if row['number'] in cls.cache_obj['loan']:
            cls.raise_error(row, 'existing_loan')
        row['currency'] = cls.currency
        row['company'] = cls.company
        return row

    @classmethod
    def migrate_rows(cls, rows, ids):
        pool = Pool()
        Loan = pool.get('loan')
        MigratorLoanIncrement = Pool().get('migrator.loan.increment')
        to_create = {}
        for row in rows:
            try:
                row = cls.populate(row)
            except migrator.MigrateError as e:
                cls.logger.error(e)
                continue
            loan = Loan(**row)
            loan.init_increments()
            to_create[row[cls.func_key]] = loan

        if to_create:
            Loan.save(to_create.values())
            Loan.calculate_loan(to_create.values())
            increments = MigratorLoanIncrement.migrate(list(to_create.keys()))
            for loan in to_create.values():
                if increments and loan.number in increments:
                    loan.state = 'draft'
                    loan.increments = increments[loan.number]
                    loan.save()
                    loan.calculate()
            Loan.save(to_create.values())
        return to_create

    @classmethod
    def sanitize(cls, row):
        err = None
        # Set defaults for optional fields
        if 'duration_unit' not in row:
            row['duration_unit'] = 'month'
        row = super(MigratorLoan, cls).sanitize(row)
        # Check that selection values are known
        if row['kind'] not in ('fixed_rate', 'interest_free', 'intermediate',
                'balloon'):
            err = cls.error_message('unknown_kind') % (
                row[cls.func_key], row['kind'])
        if row['payment_frequency'] not in ('month', 'quarter', 'half_year',
                'year'):
            err = cls.error_message('unknown_payment_frequency') % (
                row[cls.func_key], row['payment_frequency'])
        if row['deferral'] not in (None, '', 'partially', 'fully'):
            err = cls.error_message('unknown_deferral') % (
                row[cls.func_key], row['deferral'])
        # Check for incoherent values
        if row['kind'] == 'interest_free' and row['rate']:
            err = cls.error_message('non_zero_rate') % (
                row[cls.func_key], row['rate'])
        if row['kind'] != 'interest_free' and not row['rate']:
            err = cls.error_message('zero_rate') % row[cls.func_key]
        if err:
            cls.logger.error(err)
            return  # skip row
        row['state'] = 'draft'
        return row
