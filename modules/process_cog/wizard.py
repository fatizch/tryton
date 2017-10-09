# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os

from trytond.wizard import StateTransition, Button, StateView
from trytond.tools import file_open

from trytond.modules.coog_core import model, fields
from trytond.modules.coog_core.export import ExportImportMixin


__all__ = [
    'ImportProcessDisplayer',
    'ImportProcessSelect',
    'ImportProcess',
    ]


class ImportProcessDisplayer(model.CoogView):
    'Import Process Displayer'

    __name__ = 'import.process.displayer'

    name = fields.Char('Process', required=True, readonly=True)
    path = fields.Char('Path', states={
            'required': True,
            'readonly': True,
            'invisible': True,
            })
    description = fields.Text('Description', readonly=True)
    to_install = fields.Boolean('To Install')
    is_visible = fields.Boolean('Is Visible')


class ImportProcessSelect(model.CoogView):
    'Import Process Select'

    __name__ = 'import.process.select'

    processes = fields.One2Many('import.process.displayer', None,
        'Processes', required=True, readonly=True)

    def available_processes(self):
        return []


class ImportProcess(model.CoogWizard):
    'Import Process'

    __name__ = 'import.process'

    start = StateView('import.process.select',
        'process_cog.import_process_select_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Import Process', 'import_process', 'tryton-go-next',
                default=True)])
    import_process = StateTransition()

    def default_start(self, name):
        return {
            'processes': [x for x in self.start.available_processes()
                if x['is_visible']]
            }

    def transition_import_process(self):
        for to_import in self.start.processes:
            filepath = os.path.normpath(to_import.path)
            if not filepath or not to_import.to_install:
                continue
            with file_open(filepath, 'rb') as f_:
                values = f_.read()
                ExportImportMixin.import_json(str(values))
        return 'end'
