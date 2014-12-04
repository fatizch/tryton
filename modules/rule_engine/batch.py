from trytond.modules.cog_utils.batch import BatchRoot
from trytond.pool import Pool

__all__ = [
    'ValidateRuleBatch',
    ]


class ValidateRuleBatch(BatchRoot):
    'Rule Engine Test Case Validation Batch'

    __name__ = 'rule_engine.validate'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'rule_engine.test_case'

    @classmethod
    def get_batch_search_model(cls):
        return 'rule_engine.test_case'

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Pool().get('rule_engine.test_case').check_pass(objects)
