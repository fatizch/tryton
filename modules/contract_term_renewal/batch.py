# -*- coding:utf-8 -*-
from trytond.pool import Pool
from trytond.modules.cog_utils import batch


class RenewContracts(batch.BatchRoot):
    'Contracts Renewal Batch'

    __name__ = 'contract.renew'

    logger = batch.get_logger(__name__)

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
            ('end_date', '>=', treatment_date)]

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        RenewalWizard = Pool().get('contract_term_renewal.renew',
            type='wizard')
        RenewalWizard.renew_contracts(objects)
        cls.logger.info('Renewed %d contracts.' % len(objects))
