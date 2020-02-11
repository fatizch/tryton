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
    def treat_file_line(cls, line):
        # The first 4 characters of each line describes the line's length,
        # therefore we crop it
        # In each line, the separator between meaningful sections
        # is the character '@', therefore we transform each line to a list of
        # meaningful sections
        return line[4:].split('@')

    @classmethod
    def _sort_files(cls, files):
        return sorted(files, key=lambda x: x[0])

    @classmethod
    def select_ids(cls, in_directory=None, out_directory=None):
        if not in_directory and not out_directory:
            raise Exception("'in_directory', 'out_directory' are required")
        files = cls.get_file_names_and_paths(in_directory)
        files = cls._sort_files(files)
        all_elements = []
        date = None
        line_110 = None
        line_120 = None
        for file_name, file_path in files:
            with open(file_path, 'r') as _file:
                for line in _file:
                    line_contents = cls.treat_file_line(line)
                    for element in line_contents:
                        if element.startswith('000'):
                            date = element[55:61]
                        elif element.startswith("110"):
                            line_110 = element
                        elif element.startswith("120"):
                            line_120 = element
                        elif element.startswith("290"):
                            line_290 = element
                            all_elements.extend(
                                [(date, line_110, line_120, line_290)])
            shutil.move(file_path, out_directory)

        return all_elements

    @classmethod
    def _covered_element_from_element(cls, element):
        CoveredElement = Pool().get('contract.covered_element')
        line_110 = element[1]
        line_120 = element[2]
        ssn = line_110[5:20]
        birth_date = None
        if line_120[5:11] != '000000':
            birth_date = datetime.datetime.strptime(
                line_120[5:11], '%d%m%y').date()
            birth_order = line_120[11:12]

        domain = [
            ('party.ssn', '=', ssn),
            ]
        if birth_date:
            domain.extend([
                ('party.birth_date', '=', birth_date),
                ('party.birth_order', '=', int(birth_order)),
                ])
        return CoveredElement.search(domain)

    @classmethod
    def execute(cls, objects, ids, in_directory, out_directory):
        for element in objects:
            noemie_update_date = datetime.datetime.strptime(
                element[0], '%y%m%d')
            noemie_return_code = element[3][14:16]
            if noemie_return_code not in dict(NOEMIE_CODE):
                logging.getLogger('contract.noemie.flow.batch').warning(
                    'Unknown return code %s' % noemie_return_code)
            else:
                CoveredElement = Pool().get('contract.covered_element')
                covered_elements = cls._covered_element_from_element(element)
                if covered_elements:
                    CoveredElement.update_noemie_status(
                        covered_elements, noemie_return_code,
                        noemie_update_date)
                else:
                    logging.getLogger('contract.noemie.flow.batch').warning(
                        'Unknown covered element with ssn %s' % element[
                            1][5:20])
