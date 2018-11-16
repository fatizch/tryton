# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from os.path import join as pjoin
from trytond.pool import Pool, PoolMeta
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.modules.coog_core import fields, model

__all__ = [
    'ClaimPasrauUploadWizard',
    'ClaimPasrauSelectFile',
    'ClaimPasrauImportFileSummary',
    ]


class ClaimPasrauUploadWizard(Wizard):
    'Claim Pasrau File Upload Wizard'
    __name__ = 'claim.pasrau.upload.wizard'

    start_state = 'file_selection'
    file_selection = StateView('claim.pasrau.select_file',
        'claim_pasrau.select_file_displayer', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Validate', 'process_pasrau_file', 'tryton-go-next',
                default=True)])
    process_pasrau_file = StateTransition()
    process_summary = StateView('claim.pasrau.file_import_summary',
        'claim_pasrau.import_file_summary_form_view', [
            Button('OK', 'end', 'tryton-ok', default=True)])

    @classmethod
    def __setup__(cls):
        super(ClaimPasrauUploadWizard, cls).__setup__()
        cls._error_messages.update({
                'invalid_file': 'The file is not valid',
                })

    def transition_process_pasrau_file(self):
        if not self.file_selection.file:
            self.raise_user_error('invalid_file')
        filepath = pjoin('/tmp', self.file_selection.file_name)
        tmp_file = open(filepath, 'w')
        tmp_file.write(self.file_selection.file)
        tmp_file.close()
        PartyCustomPasrauRate = Pool().get('party.pasrau.rate')
        self.file_selection.created_rates, self.file_selection.errors = \
            PartyCustomPasrauRate.process_xml_file(filepath)
        return 'process_summary'

    def default_process_summary(self, name):
        return {
            'created_rates': [x.id for x in self.file_selection.created_rates],
            'errors': '\n'.join(self.file_selection.errors)
            }


class ClaimPasrauSelectFile(model.CoogView):
    'Claim Pasrau Select File'
    __name__ = 'claim.pasrau.select_file'

    file = fields.Binary('File', filename='file_name')
    file_name = fields.Char('File Name')

    @staticmethod
    def default_file_name():
        return 'pasrau-crm.xml'


class ClaimPasrauImportFileSummary(model.CoogView):
    'Claim Pasrau Select File'
    __name__ = 'claim.pasrau.file_import_summary'

    created_rates = fields.One2Many('party.pasrau.rate', None, 'Created Rate',
        readonly=True)
    errors = fields.Text('Errors', readonly=True)


class InvoiceSlipParameters:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.slip.parameters'

    @classmethod
    def __setup__(cls):
        super(InvoiceSlipParameters, cls).__setup__()
        cls.slip_kind.selection.append(
            ('pasrau', 'Pasrau'))
