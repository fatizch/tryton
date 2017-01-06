# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool

from trytond.modules.coog_core import batch


__all__ = [
    'ProductValidationBatch',
    ]


class ProductValidationBatch(batch.BatchRoot):
    'Product Validation Batch'

    __name__ = 'offered.validate'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'offered.product'

    @classmethod
    def get_batch_search_model(cls):
        return 'offered.product'

    @classmethod
    def execute(cls, objects, ids):
        # TODO : explode ModelStorage._validate in smaller functions that could
        # be individually called.
        # That would permit to see every test that failed, whereas as of the
        # current version, only the first error of all the batch of records is
        # reported
        Product = Pool().get('offered.product')
        Product._validate(objects)
        cls.logger.info('Validated %d products' % len(objects))
