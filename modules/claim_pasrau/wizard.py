# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from os.path import join as pjoin
from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.modules.coog_core import fields, model

__all__ = [
    'ClaimPasrauUploadWizard',
    'ClaimPasrauSelectFile',
    ]


class ClaimPasrauUploadWizard(Wizard):
    'Claim Pasrau File Upload Wizard'
    __name__ = 'claim.pasrau.upload.wizard'

    start_state = 'file_selection'
    file_selection = StateView('claim.pasrau.select_file',
        'claim_pasrau.select_file_displayer', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Validate', 'process_pasrau_file', 'tryton-go-next')])
    process_pasrau_file = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ClaimPasrauUploadWizard, cls).__setup__()
        cls._error_messages.update({
                'process_error': 'The file could not be processed',
                })

    def transition_process_pasrau_file(self):
        if not self.file_selection.file:
            return 'end'
        filepath = pjoin('/tmp', self.file_selection.file_name)
        tmp_file = open(filepath, 'w')
        tmp_file.write(self.file_selection.file)
        tmp_file.close()
        PartyCustomPasrauRate = Pool().get('party.pasrau.rate')
        if PartyCustomPasrauRate.process_xml_file(filepath) is False:
            self.raise_user_warning('process_error')
            return 'end'
        return 'end'


class ClaimPasrauSelectFile(model.CoogView):
    'Claim Pasrau Select File'
    __name__ = 'claim.pasrau.select_file'

    file = fields.Binary('File', filename='file_name')
    file_name = fields.Char('File Name')

    @staticmethod
    def default_file_name():
        return 'pasrau-crm.xml'
