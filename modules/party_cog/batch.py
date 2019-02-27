# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool
from trytond.error import UserError
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch

__all__ = [
    'PartyAnonymizeBatch',
    ]


class PartyAnonymizeBatch(batch.BatchRoot):
    'Anonymize Parties batch'

    __name__ = 'party.anonymize.process'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(PartyAnonymizeBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'party.party'

    @classmethod
    def select_ids(cls, treatment_date):
        pool = Pool()
        party = pool.get('party.party').__table__()
        cursor = Transaction().connection.cursor()

        cursor.execute(*party.select(party.id,
                where=party.planned_anonymization_date <= treatment_date))
        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Party = Pool().get('party.party')
        for party in objects:
            try:
                party.active = False
                party.save()
                Party.anonymize(party.id)
            except UserError as e:
                cls.logger.warning(e.message)
                continue
