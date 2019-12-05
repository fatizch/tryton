# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool

from trytond.modules.coog_core import batch, utils

__all__ = [
    'BankImport'
    ]


class BankImport(batch.BatchRootNoSelect):
    'Bank Import'

    __name__ = 'bank_cog.data.import'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(BankImport, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 1,
                })

    @classmethod
    def select_ids(cls, in_directory, archive):
        if not in_directory or not archive:
            raise Exception("'in_directory', 'archive' are required")
        files = cls.get_file_names_and_paths(in_directory)
        return [f[1] for f in files]

    @classmethod
    def execute(cls, objects, ids, in_directory, archive):
        BankWizard = Pool().get('bank_cog.data.set.wizard', type='wizard')
        configuration = Pool().get('party.configuration')(1)
        wizard_id, _, _ = BankWizard.create()
        bank_wiz = BankWizard(wizard_id)
        treated_files = []
        for file_path in objects:
            with open(file_path, 'rb') as _file:
                data = {
                    'file_format': 'swift',
                    'use_default': False,
                    'resource': _file.read(),
                    'countries_to_import': [
                        {'id': country.id, 'code': country.code}
                        for country in configuration.bic_swift_countries]}
            bank_wiz.execute(wizard_id, {'configuration': data},
                'configuration')
            bank_wiz.execute(wizard_id, {}, 'set_')
            treated_files.append((file_path.split('/')[-1], file_path))

        cls.archive_treated_files(treated_files,
            archive, utils.today())
