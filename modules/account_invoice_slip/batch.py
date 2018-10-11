# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool

from trytond.modules.coog_core import batch

__all__ = [
    'CreateEmptySlipBatch',
    'LinkSlipBatch',
    'FinalizeSlipBatch',
    ]


class CreateEmptySlipBatch(batch.BatchRootNoSelect):
    'Empty Slip Creation Batch'

    __name__ = 'account.invoice.slip.create_empty'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_slip_configurations(cls, date):
        Configuration = Pool().get('account.invoice.slip.configuration')

        slip_parameters = []
        for configuration in Configuration.search([]):
            params_dict = configuration.get_params_dict()
            params_dict['date'] = date
            slip_parameters.append(params_dict)
        return slip_parameters

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        SlipConfiguration = Pool().get('account.invoice.slip.configuration')

        parameters = cls.get_slip_configurations(treatment_date)
        if parameters:
            SlipConfiguration.create_empty_slips(parameters)


class LinkSlipBatch(batch.BatchRoot):
    'Slip Link Batch'

    __name__ = 'account.invoice.slip.link'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def select_ids(cls, treatment_date):
        pool = Pool()
        CreateEmpty = pool.get('account.invoice.slip.create_empty')
        Slip = pool.get('account.invoice.slip.configuration')

        parameters = CreateEmpty.get_slip_configurations(treatment_date)
        invoices_ids = Slip.select_invoices(parameters)
        return ([[invoice]] for invoice in invoices_ids)

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        pool = Pool()
        CreateEmpty = pool.get('account.invoice.slip.create_empty')
        Slip = pool.get('account.invoice.slip.configuration')

        parameters = CreateEmpty.get_slip_configurations(treatment_date)
        if parameters:
            Slip.update_slips_from_invoices(parameters, ids)


class FinalizeSlipBatch(batch.BatchRootNoSelect):
    'Slip Finalize Batch'

    __name__ = 'account.invoice.slip.finalize'

    logger = logging.getLogger(__name__)

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        pool = Pool()
        SlipConfiguration = pool.get('account.invoice.slip.configuration')
        CreateEmpty = pool.get('account.invoice.slip.create_empty')

        parameters = CreateEmpty.get_slip_configurations(treatment_date)
        if parameters:
            SlipConfiguration.finalize_slips(parameters)
