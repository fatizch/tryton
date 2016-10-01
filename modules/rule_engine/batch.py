# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.modules.coog_core import batch
from trytond.pool import Pool

__all__ = [
    'ValidateRuleBatch',
    ]


class ValidateRuleBatch(batch.BatchRoot):
    'Rule Engine Test Case Validation Batch'

    __name__ = 'rule_engine.validate'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'rule_engine.test_case'

    @classmethod
    def get_batch_search_model(cls):
        return 'rule_engine.test_case'

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        Pool().get('rule_engine.test_case').check_pass(objects)
        cls.logger.info('%s objects validated' % len(objects))

    @classmethod
    def get_batch_args_name(cls):
        return []
