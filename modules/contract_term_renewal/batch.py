# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool
from trytond.modules.coog_core import batch


class RenewContracts(batch.BatchRoot):
    'Contracts Renewal Batch'

    __name__ = 'contract.renew'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def get_batch_search_model(cls):
        return 'contract'

    @classmethod
    def get_batch_domain(cls, treatment_date, extra_args):
        pool = Pool()
        Product = pool.get('offered.product')
        renewable_products = Product.search([
                ('term_renewal_rule.allow_renewal', '=', True)])
        return [
            ('status', '=', 'active'),
            ('end_date', '!=', None),
            ('product', 'in', renewable_products),
            ('activation_history.final_renewal', '!=', True),
            ('end_date', '<=', treatment_date)]

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        RenewalWizard = Pool().get('contract_term_renewal.renew',
            type='wizard')
        renewed = RenewalWizard.renew_contracts(objects)
        cls.logger.info('Renewed %d contracts.' % len(renewed))

    @classmethod
    def get_batch_args_name(cls):
        return []
