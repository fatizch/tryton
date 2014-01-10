from trytond.pool import Pool
from trytond.error import UserError

from trytond.modules.cog_utils import BatchRoot

__all___ = [
    'ProductValidationBatch',
    ]


class ProductValidationBatch(BatchRoot):
    'Product Validation Batch'

    __name__ = 'offered.validate.batch'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'offered.product'

    @classmethod
    def get_batch_search_model(cls):
        return 'offered.product'

    @classmethod
    def get_batch_name(cls):
        return 'Product Validation Batch'

    @classmethod
    def execute(cls, objects, ids, logger):
        # TODO : explose ModelStorage._validate in smaller functions that could
        # be individually called.
        # That would permit to see every test that failed, whereas as of the
        # current version, only the first error of all the batch of records is
        # reported
        Product = Pool().get('offered.product')
        logger.info('Validating products %s' % objects)
        try:
            Product._validate(objects)
        except UserError as exc:
            logger.warning('Bad validation : %s' % exc)

    @classmethod
    def get_batch_stepping_mode(cls):
        return 'divide'

    @classmethod
    def get_batch_step(cls):
        return 2
