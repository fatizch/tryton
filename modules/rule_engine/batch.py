from trytond.modules.cog_utils import batch
from trytond.pool import Pool

__all__ = [
    'ValidateRuleBatch',
    ]


class ValidateRuleBatch(batch.BatchRoot):
    'Rule Engine Test Case Validation Batch'

    __name__ = 'rule_engine.validate'

    logger = batch.get_logger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'rule_engine.test_case'

    @classmethod
    def get_batch_search_model(cls):
        return 'rule_engine.test_case'

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Pool().get('rule_engine.test_case').check_pass(objects)
        cls.logger.success('%s objects validated' % len(objects))
