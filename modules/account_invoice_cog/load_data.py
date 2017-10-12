# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = [
    'FiscalYearSetWizard',
    ]


class FiscalYearSetWizard:

    __metaclass__ = PoolMeta
    __name__ = 'fiscal_year.set.wizard'

    @classmethod
    def new_fiscal_year(cls, start_date):
        pool = Pool()
        Company = pool.get('company.company')
        company = Company(Transaction().context.get('company'))

        Sequence = pool.get('ir.sequence.strict')
        result = super(FiscalYearSetWizard, cls).new_fiscal_year(start_date)
        FiscalYearInvoiceSequence = pool.get(
            'account.fiscalyear.invoice_sequence')

        in_credit_note_sequence = Sequence(**{
                'company': company,
                'name': '%s - %s %s' % (
                    cls.translate('in_credit_note_sequence'),
                    cls.translate('fiscal_year'), start_date.year),
                'code': 'account.invoice',
                'prefix': str(start_date.year),
                'padding': 9,
                })
        in_invoice_sequence = Sequence(**{
                'company': company,
                'name': '%s - %s %s' % (cls.translate('in_invoice_sequence'),
                    cls.translate('fiscal_year'), start_date.year),
                'code': 'account.invoice',
                'prefix': str(start_date.year),
                'padding': 9,
                })
        out_credit_note_sequence = Sequence(**{
                'company': company,
                'name': '%s - %s %s' % (
                    cls.translate('out_credit_note_sequence'),
                    cls.translate('fiscal_year'), start_date.year),
                'code': 'account.invoice',
                'prefix': str(start_date.year),
                'padding': 9,
                })
        out_invoice_sequence = Sequence(**{
                'company': company,
                'name': '%s - %s %s' % (cls.translate('out_invoice_sequence'),
                    cls.translate('Fiscal Year'), start_date.year),
                'code': 'account.invoice',
                'prefix': str(start_date.year),
                'padding': 9,
                })
        invoice_sequence = FiscalYearInvoiceSequence(**{
                'in_credit_note_sequence': in_credit_note_sequence,
                'in_invoice_sequence': in_invoice_sequence,
                'out_credit_note_sequence': out_credit_note_sequence,
                'out_invoice_sequence': out_invoice_sequence,
                })
        result.invoice_sequences = [invoice_sequence]
        return result
