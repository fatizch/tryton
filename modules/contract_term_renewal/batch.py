# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import logging

from sql import Literal, Window
from sql.conditionals import Coalesce
from sql.aggregate import Max

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.modules.coog_core import batch


class RenewContracts(batch.BatchRoot):
    'Contracts Renewal Batch'

    __name__ = 'contract.renew'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def select_ids(cls, treatment_date):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        Product = pool.get('offered.product')
        renewable_products = [x.id for x in Product.search([
                    ('term_renewal_rule.allow_renewal', '=', True)])]
        contract = pool.get('contract').__table__()
        activation_history = pool.get('contract.activation_history'
            ).__table__()
        win_query = activation_history.select(
            activation_history.contract,
            activation_history.active,
            activation_history.final_renewal,
            Coalesce(activation_history.end_date,
                datetime.date.max).as_('end_date'),
            Max(Coalesce(activation_history.end_date, datetime.date.max),
                window=Window([activation_history.contract])).as_('max_end'),
            )
        cursor.execute(*contract.join(win_query,
                condition=win_query.contract == contract.id
                ).select(contract.id, where=(contract.status == 'active')
                & contract.product.in_(renewable_products)
                & (win_query.end_date == win_query.max_end)
                & (win_query.end_date <= treatment_date)
                & (win_query.final_renewal == Literal(False))))
        return [x for x in cursor.fetchall()]

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        RenewalWizard = Pool().get('contract_term_renewal.renew',
            type='wizard')
        renewed = RenewalWizard.renew_contracts(objects)
        cls.logger.info('Renewed %d contracts.' % len(renewed))
