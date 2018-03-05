# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from collections import defaultdict

from trytond.pool import Pool
from trytond.error import UserError

from trytond.modules.coog_core import batch


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
    def get_batch_domain(cls, treatment_date):
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
    def execute(cls, objects, ids, treatment_date):
        pool = Pool()
        Service = pool.get('claim.service')
        indemnifications = Service.create_indemnifications(objects,
            treatment_date)
        cls.schedule_indemnifications(indemnifications)

    @classmethod
    def schedule_indemnifications(cls, indemnifications):
        if not indemnifications:
            return
        Indemnification = Pool().get('claim.indemnification')
        indemnifications_to_schedule = []
        indemn_by_service = defaultdict(list)
        for indemnification in indemnifications:
            indemn_by_service[indemnification.service].append(indemnification)
        for service_indemnifications in indemn_by_service.values():
            sorted_indemnifications = sorted(service_indemnifications,
                key=lambda x: x.start_date)
            try:
                Indemnification.check_schedulability(sorted_indemnifications)
                indemnifications_to_schedule.extend(sorted_indemnifications)
            except UserError:
                continue
        Indemnification.do_schedule(indemnifications_to_schedule)
