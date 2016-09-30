# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool

from trytond.modules.cog_utils import batch


__all__ = [
    'CreateClaimIndemnificationBatch',
    ]


class CreateClaimIndemnificationBatch(batch.BatchRoot):
    'Create Claim Idemnification Batch'

    __name__ = 'claim.indemnification.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'claim.service'

    @classmethod
    def get_batch_search_model(cls):
        return 'claim.service'

    @classmethod
    def get_batch_domain(cls, treatment_date, extra_args):
        # don't create indemnification if paid_until_date is manual
        # First indmenification is manual
        # Can be improve by selection benefit in a separate list
        return [
            ('paid_until_date', '!=', None),
            ('paid_until_date', '<', treatment_date),
            ('benefit.indemnification_kind', '=', 'annuity'),
            ['OR', ('loss.end_date', '=', None),
                ('loss.end_date', '>=', treatment_date)],
            ]

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        Pool().get('claim.service').create_indemnifications(objects,
            treatment_date)
