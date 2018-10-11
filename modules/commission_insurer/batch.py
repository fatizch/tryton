# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool

from trytond.modules.coog_core import batch

__all__ = [
    'CreateEmptyInvoicePrincipalBatch',
    'LinkInvoicePrincipalBatch',
    'FinalizeInvoicePrincipalBatch',
    ]


class CreateEmptyInvoicePrincipalBatch(batch.BatchRootNoSelect):
    'Insurer Empty Invoice Principal Creation Batch'

    __name__ = 'commission.invoice_principal.create_empty'

    logger = logging.getLogger(__name__)

    @classmethod
    def possible_notice_kinds(cls):
        CreateNoticeAsk = Pool().get('commission.create_invoice_principal.ask')
        return [x[0] for x in CreateNoticeAsk.notice_kind.selection]

    @classmethod
    def parse_params(cls, params):
        params = super(CreateEmptyInvoicePrincipalBatch, cls).parse_params(
            params)
        assert params.get('notice_kind') in cls.possible_notice_kinds()
        return params

    @classmethod
    def get_slip_configurations(cls, treatment_date, notice_kind):
        pool = Pool()
        Insurer = pool.get('insurer')
        Journal = pool.get('account.journal')

        parameters = Insurer.generate_slip_parameters(notice_kind)
        journal, = Journal.search([('type', '=', 'commission')])

        for parameter in parameters:
            parameter['journal'] = journal
            parameter['date'] = treatment_date
        return parameters

    @classmethod
    def execute(cls, objects, ids, treatment_date, notice_kind):
        pool = Pool()
        Slip = pool.get('account.invoice.slip.configuration')

        parameters = cls.get_slip_configurations(treatment_date, notice_kind)
        if parameters:
            Slip.create_empty_slips(parameters)


class LinkInvoicePrincipalBatch(batch.BatchRoot):
    'Insurer Invoice Principal Link Batch'

    __name__ = 'commission.invoice_principal.link'

    logger = logging.getLogger(__name__)

    @classmethod
    def parse_params(cls, params):
        params = super(LinkInvoicePrincipalBatch, cls).parse_params(
            params)
        CreateEmpty = Pool().get('commission.invoice_principal.create_empty')
        assert params.get('notice_kind') in CreateEmpty.possible_notice_kinds()
        return params

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def select_ids(cls, treatment_date, notice_kind=None):
        pool = Pool()
        CreateEmpty = pool.get('commission.invoice_principal.create_empty')
        Slip = pool.get('account.invoice.slip.configuration')

        parameters = CreateEmpty.get_slip_configurations(treatment_date,
            notice_kind)
        invoices_ids = Slip.select_invoices(parameters)
        return ([[invoice]] for invoice in invoices_ids)

    @classmethod
    def execute(cls, objects, ids, treatment_date, notice_kind=None):
        pool = Pool()
        CreateEmpty = pool.get('commission.invoice_principal.create_empty')
        Slip = pool.get('account.invoice.slip.configuration')

        parameters = CreateEmpty.get_slip_configurations(treatment_date,
            notice_kind)
        if parameters:
            Slip.update_slips_from_invoices(parameters, ids)


class FinalizeInvoicePrincipalBatch(batch.BatchRootNoSelect):
    'Insurer Invoice Principal Finalize Batch'

    __name__ = 'commission.invoice_principal.finalize'

    logger = logging.getLogger(__name__)

    @classmethod
    def parse_params(cls, params):
        params = super(FinalizeInvoicePrincipalBatch, cls).parse_params(
            params)
        CreateEmpty = Pool().get('commission.invoice_principal.create_empty')
        assert params.get('notice_kind') in CreateEmpty.possible_notice_kinds()
        return params

    @classmethod
    def execute(cls, objects, ids, treatment_date, notice_kind):
        pool = Pool()
        CreateEmpty = pool.get('commission.invoice_principal.create_empty')
        Slip = pool.get('account.invoice.slip.configuration')

        parameters = CreateEmpty.get_slip_configurations(treatment_date,
            notice_kind)
        if parameters:
            Slip.finalize_slips(parameters)
