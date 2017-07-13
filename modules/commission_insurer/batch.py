# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from sql import Null
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch

__all__ = [
    'CreateEmptyInvoicePrincipalBatch',
    'LinkInvoicePrincipalBatch',
    'FinalizeInvoicePrincipalBatch',
    ]


class CreateEmptyInvoicePrincipalBatch(batch.BatchRoot):
    'Insurer Empty Invoice Principal Creation Batch'

    __name__ = 'commission.invoice_principal.create_empty'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(CreateEmptyInvoicePrincipalBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                })

    @classmethod
    def parse_params(cls, params):
        params = super(CreateEmptyInvoicePrincipalBatch, cls).parse_params(
            params)
        assert params.get('job_size') == 0
        return params

    @classmethod
    def get_batch_main_model_name(cls):
        return 'insurer'

    @classmethod
    def select_ids(cls, treatment_date):
        insurer = Pool().get('insurer').__table__()
        cursor = Transaction().connection.cursor()

        cursor.execute(*insurer.select(insurer.id,
                where=(insurer.waiting_account != Null)))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        pool = Pool()
        Journal = pool.get('account.journal')
        Company = pool.get('company.company')
        CreateInvoicePrincipal = pool.get(
            'commission.create_invoice_principal', type='wizard')

        company = Company(Transaction().context.get('company'))
        journal = Journal.search([('type', '=', 'commission')], limit=1)[0]
        premium_line_description = pool.get('account.invoice'
            ).raise_user_error('batch_premiums_received',
                raise_exception=False)

        CreateInvoicePrincipal.create_empty_invoices(objects, company, journal,
            treatment_date, premium_line_description)


class LinkInvoicePrincipalBatch(batch.BatchRoot):
    'Insurer Invoice Principal Link Batch'

    __name__ = 'commission.invoice_principal.link'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'insurer'

    @classmethod
    def select_ids(cls, treatment_date):
        until_date = treatment_date
        pool = Pool()
        insurers = pool.get('insurer').search([
                ('waiting_account', '!=', None)])

        invoices = pool.get('commission').select_lines(
                [a.waiting_account.id for a in insurers], with_data=False,
                max_date=until_date)
        return ([[invoice]] for invoice in invoices)

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        pool = Pool()
        Journal = pool.get('account.journal')
        Company = pool.get('company.company')
        CreateInvoicePrincipal = pool.get(
            'commission.create_invoice_principal', type='wizard')
        insurers = Pool().get('insurer').search([
                ('waiting_account', '!=', None)])

        company = Company(Transaction().context.get('company'))
        journal = Journal.search([('type', '=', 'commission')], limit=1)[0]

        premium_line_description = pool.get('account.invoice'
            ).raise_user_error('batch_premiums_received',
                raise_exception=False)
        CreateInvoicePrincipal.link_invoices_and_lines(
            insurers, treatment_date, company, journal,
            premium_line_description, invoice_ids=ids)


class FinalizeInvoicePrincipalBatch(batch.BatchRoot):
    'Insurer Invoice Principal Finalize Batch'

    __name__ = 'commission.invoice_principal.finalize'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(FinalizeInvoicePrincipalBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                })

    @classmethod
    def parse_params(cls, params):
        params = super(FinalizeInvoicePrincipalBatch, cls).parse_params(params)
        assert params.get('job_size') == 0
        return params

    @classmethod
    def get_batch_main_model_name(cls):
        return 'insurer'

    @classmethod
    def select_ids(cls, treatment_date):
        insurer = Pool().get('insurer').__table__()
        cursor = Transaction().connection.cursor()

        cursor.execute(*insurer.select(insurer.id,
            where=(insurer.waiting_account != Null)))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        pool = Pool()
        Journal = pool.get('account.journal')
        Company = pool.get('company.company')
        CreateInvoicePrincipal = pool.get(
            'commission.create_invoice_principal', type='wizard')
        company = Company(Transaction().context.get('company'))
        journal = Journal.search([('type', '=', 'commission')], limit=1)[0]

        premium_line_description = pool.get('account.invoice'
            ).raise_user_error('batch_premiums_received',
                raise_exception=False)
        CreateInvoicePrincipal.finalize_invoices_and_lines(
            objects, company, journal, treatment_date,
            premium_line_description)
