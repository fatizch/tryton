# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import logging
import shutil

from trytond.pool import Pool

from trytond.modules.coog_core import batch

__all__ = [
    'UpdatePartyPasrauRateBatch',
    ]


class UpdatePartyPasrauRateBatch(batch.BatchRoot):
    'Update Party Pasrau Rate Batch'

    __name__ = 'party.pasrau.rate.batch'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(UpdatePartyPasrauRateBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                'split': False,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'party.pasrau.rate'

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return ids[:]

    @classmethod
    def select_ids(cls, directory):
        for file_ in os.listdir(directory):
            if file_.endswith('.xml'):
                yield (os.path.join(directory, file_), )

    @classmethod
    def execute(cls, objects, ids, directory):
        PartyCustomPasrauRate = Pool().get('party.pasrau.rate')
        archive_dir = os.path.join(directory, 'archive')
        logger = cls.logger
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
        for filepath in ids:
            to_archive = False
            if PartyCustomPasrauRate.process_xml_file(filepath, logger=logger):
                to_archive = True
            if to_archive:
                shutil.move(filepath, archive_dir)
