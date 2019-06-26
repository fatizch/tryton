# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import shutil
import datetime
import logging

from trytond.pool import Pool
from trytond.modules.coog_core import batch

from .contract import NOEMIE_CODE


__all__ = [
    'ContractNoemieFlowBatch',
    ]


class ContractNoemieFlowBatch(batch.BatchRootNoSelect):
    'Contract Noemie Flow Batch'

    __name__ = 'contract.noemie.flow.batch'

    @classmethod
    def __setup__(cls):
        super(ContractNoemieFlowBatch, cls).__setup__()
        cls._default_config_items.update({
            'split': True,
            })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract.covered_element'

    @classmethod
    def select_ids(cls, in_directory=None, out_directory=None):
        if not in_directory and not out_directory:
            raise Exception("'in_directory', 'out_directory' are required")
        files = cls.get_file_names_and_paths(in_directory)
        all_elements = []
        date = None
        line_140 = None
        for file_name, file_path in files:
            with open(file_path, 'r') as _file:
                for x in _file:
                    if x.startswith('000'):
                        date = x[55:61]
                    elif x.startswith("140"):
                        line_140 = x
                    elif x.startswith("290"):
                        line_290 = x
                        all_elements.extend([(date, line_140, line_290)])
            shutil.move(file_path, out_directory)

        return all_elements

    @classmethod
    def execute(cls, objects, ids, in_directory, out_directory):
        for element in objects:
            party_code = element[1][5:13].strip()
            noemie_update_date = datetime.datetime.strptime(
                element[0], '%y%m%d')
            noemie_return_code = element[2][14:16]
            if noemie_return_code not in dict(NOEMIE_CODE):
                logging.getLogger('contract.noemie.flow.batch').warning(
                    'Unknown return code %s' % noemie_return_code)
            else:
                CoveredElement = Pool().get('contract.covered_element')
                covered_elements = CoveredElement.search([
                    ('party.code', '=', party_code)])
                if covered_elements:
                    CoveredElement.update_noemie_status(
                        covered_elements, noemie_return_code,
                        noemie_update_date)
