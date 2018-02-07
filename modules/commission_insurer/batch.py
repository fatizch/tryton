# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch

__all__ = [
    'CreateEmptyInvoicePrincipalBatch',
    'LinkInvoicePrincipalBatch',
    'FinalizeInvoicePrincipalBatch',
    ]


class BaseInvoicePrincipalBatch(batch.BatchRoot):

    @classmethod
    def possible_notice_kind(cls):
        return ('options',)

    @classmethod
    def parse_params(cls, params):
        params = super(BaseInvoicePrincipalBatch, cls).parse_params(
            params)
        assert params.get('notice_kind') in cls.possible_notice_kind()
        return params

    @classmethod
    def get_principal_line_description(cls, notice_kind):
        if notice_kind == 'options':
            return Pool().get('account.invoice'
            ).raise_user_error('batch_premiums_received',
                raise_exception=False)
        raise NotImplementedError

    @classmethod
    def get_insurers(cls, notice_kind):
        if notice_kind == 'options':
            Insurer = Pool().get('insurer')
            return Insurer.search([
                    ('options.account_for_billing', '!=', None)
                    ])
        raise NotImplementedError


class CreateEmptyInvoicePrincipalBatch(BaseInvoicePrincipalBatch):
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
    def select_ids(cls, treatment_date, notice_kind=None):
        return [(x.id,) for x in cls.get_insurers(notice_kind)]

    @classmethod
    def execute(cls, objects, ids, treatment_date, notice_kind=None):
        pool = Pool()
        Journal = pool.get('account.journal')
        Company = pool.get('company.company')
        CreateInvoicePrincipal = pool.get(
            'commission.create_invoice_principal', type='wizard')

        company = Company(Transaction().context.get('company'))
        journal = Journal.search([('type', '=', 'commission')], limit=1)[0]
        line_description = cls.get_principal_line_description(
            notice_kind)

        CreateInvoicePrincipal.create_empty_invoices(objects, company, journal,
            treatment_date, line_description, notice_kind)


class LinkInvoicePrincipalBatch(BaseInvoicePrincipalBatch):
    'Insurer Invoice Principal Link Batch'

    __name__ = 'commission.invoice_principal.link'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'insurer'

    @classmethod
    def select_ids(cls, treatment_date, notice_kind=None):
        until_date = treatment_date
        pool = Pool()

        Insurer = pool.get('insurer')
        insurers = cls.get_insurers(notice_kind)

        accounts = [x[1].id for x in
            Insurer.get_insurers_waiting_accounts(insurers, notice_kind)]
        invoices = pool.get('commission').select_lines(accounts,
                with_data=False, max_date=until_date)
        return ([[invoice]] for invoice in invoices)

    @classmethod
    def execute(cls, objects, ids, treatment_date, notice_kind=None):
        pool = Pool()
        Journal = pool.get('account.journal')
        Company = pool.get('company.company')
        CreateInvoicePrincipal = pool.get(
            'commission.create_invoice_principal', type='wizard')
        insurers = cls.get_insurers(notice_kind)

        company = Company(Transaction().context.get('company'))
        journal = Journal.search([('type', '=', 'commission')], limit=1)[0]

        line_description = cls.get_principal_line_description(
            notice_kind)

        CreateInvoicePrincipal.link_invoices_and_lines(
            insurers, treatment_date, company, journal,
            line_description, notice_kind, invoice_ids=ids)


class FinalizeInvoicePrincipalBatch(BaseInvoicePrincipalBatch):
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
    def select_ids(cls, treatment_date, notice_kind=None):
        return [(x.id,) for x in cls.get_insurers(notice_kind)]

    @classmethod
    def execute(cls, objects, ids, treatment_date, notice_kind=None):
        pool = Pool()
        Journal = pool.get('account.journal')
        Company = pool.get('company.company')
        CreateInvoicePrincipal = pool.get(
            'commission.create_invoice_principal', type='wizard')
        company = Company(Transaction().context.get('company'))
        journal = Journal.search([('type', '=', 'commission')], limit=1)[0]

        line_description = cls.get_principal_line_description(
            notice_kind)
        CreateInvoicePrincipal.finalize_invoices_and_lines(
            objects, company, journal, treatment_date,
            line_description, notice_kind)
