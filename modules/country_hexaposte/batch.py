# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from trytond.pool import Pool
from trytond.modules.cog_utils import batch

from .hexa_post import HexaPostLoader


class UpdateZipCodesFromHexaPost(batch.BatchRootNoSelect):
    'Update Zip Codes From Hexa Post Files'

    __name__ = 'country.zipcode.update_from_hexapost'

    logger = logging.getLogger(__name__)

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        Zip = Pool().get('country.zip')
        hexa_post_file_path = extra_args.get('hexa_post_file_path',
            cls.get_conf_item('hexa_post_file_path'))
        archive_path = extra_args.get('archive')
        if not hexa_post_file_path:
            raise Exception('Hexapost file path missing in '
                'either arguments or batch configuration file')
        files = cls.get_file_names_and_paths(hexa_post_file_path)
        if not files:
            cls.logger.info('No file at %s' % hexa_post_file_path)
            return
        file_path = files[0][1]
        with open(file_path) as f:
            hexa_data = HexaPostLoader.get_hexa_post_data_from_file(f)
        to_create, to_write = HexaPostLoader.get_hexa_post_updates(hexa_data)
        if to_create:
            Zip.create(to_create)
            cls.logger.info('Successfully created %s new zipcodes' %
                len(to_create))
        if to_write:
            Zip.write(*to_write)
            cls.logger.info('Successfully updated %s zipcodes' %
                str(len(to_write) / 2))
        else:
            cls.logger.info('No zipcode to update')
        cls.archive_treated_files(files, archive_path, treatment_date)
