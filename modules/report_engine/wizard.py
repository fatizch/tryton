# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.protocols.jsonrpc import JSONDecoder
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    Button

from trytond.modules.coog_core import fields, model


__all__ = [
    'PrintUnboundReport',
    'PrintUnboundReportStart',
    ]


class PrintUnboundReport(Wizard):
    'Print Ubound Report'

    __name__ = 'report.template.print_unbound'

    start = StateView('report.template.print_unbound.start',
        'report_engine.print_unbound_template_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'generate', 'tryton-go-next', default=True,
                states={'readonly': ~Eval('template')})])
    generate = StateTransition()
    open_document = StateAction('report_engine.generate_file_report')

    def transition_generate(self):
        pool = Pool()
        Template = pool.get('report.template')
        ReportModel = pool.get('report.generate', type='report')

        if self.start.data_file:
            data = json.loads(str(self.start.data_file),
                object_hook=JSONDecoder())
        else:
            data = {}

        data = Template._instantiate_from_data(data)
        result = self.start.template._generate_report([data], {
                'resource': data})
        _, server_filepath = ReportModel.edm_write_tmp_report(
            result['data'], result['report_name'])
        self.start.file_path = server_filepath
        return 'open_document'

    def do_open_document(self, action):
        return action, {'output_report_filepath': self.start.file_path}


class PrintUnboundReportStart(model.CoogView):
    'Print Unbound Report Start'

    __name__ = 'report.template.print_unbound.start'

    template = fields.Many2One('report.template', 'Template', required=True,
        domain=[('on_model', '=', None)])
    parameters = fields.Dict('report.template.parameter', 'Parameters',
        states={'invisible': ~Eval('parameters')}, depends=['parameters'])
    data_file = fields.Binary('Data file')
    file_path = fields.Char('File Path', states={'invisible': True})

    @fields.depends('parameters', 'template')
    def on_change_template(self):
        if not self.template:
            self.parameters = {}
        else:
            self.parameters = {x.name: None for x in self.template.parameters}
