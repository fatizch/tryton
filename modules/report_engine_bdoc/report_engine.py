# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from zeep import Client
import logging

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.config import config
from trytond.i18n import gettext

from trytond.modules.coog_core import fields
from trytond.server_context import ServerContext

BDOC_FORMAT = [
    ('', ''),
    ('docx', 'DOCX'),
    ('pdf', 'PDF'),
    ('pdfa', 'PDFA'),
    ('html', 'HTML'),
    ('html_email', ' HTML_EMAIL')
    ]
__all__ = [
    'ReportTemplate',
    'ReportGenerate',
    'ReportTemplateVersion',
    ]


class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    BDOC_production_format = fields.Selection(BDOC_FORMAT,
        'BDOC production format',
        states={'invisible': Eval('input_kind') != 'bdoc',
            'required': Eval('input_kind') == 'bdoc'},
        help='The bdoc file will be generated in this format')
    BDOC_template_domain = fields.Char('BDOC template domain',
        states={'invisible': Eval('input_kind') != 'bdoc',
            'required': Eval('input_kind') == 'bdoc'},
        help='The domain of the report template')

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        cls.export_dir.states = {
            'invisible': (Eval('input_kind') == 'bdoc')}
        cls.modifiable_before_printing.states = {
            'invisible': (Eval('input_kind') == 'bdoc') |
                         (Eval('input_kind') == 'shared_genshi_template')}

    @classmethod
    def get_possible_input_kinds(cls):
        return super().get_possible_input_kinds() + [
            ('bdoc', 'BDOC'),
        ]

    @fields.depends('process_method', 'output_format')
    def get_available_formats(self):
        available_format = super().get_available_formats()
        if self.process_method == 'bdoc':
            available_format += [('original',
                gettext('report_engine.msg_format_original'))]
        return available_format

    @fields.depends('input_kind', 'versions')
    def on_change_input_kind(self):
        super().on_change_input_kind()
        if self.input_kind == 'bdoc':
            self.export_dir = ''
            for version in self.versions:
                version.is_shared_template = True

    def get_export_dirname(self):
        if self.input_kind == 'bdoc':
            return config.get('bdoc', 'export_root_dir', default='/export_dir')
        return super().get_export_dirname()

    @fields.depends('input_kind')
    def get_possible_process_methods(self):
        if self.input_kind == 'bdoc':
            return [('bdoc', 'BDOC')]
        else:
            return super().get_possible_process_methods()

    def _must_export_generated_file(self):
        if self.input_kind == 'bdoc':
            return True
        return super()._must_export_generated_file()


class ReportGenerate(metaclass=PoolMeta):
    __name__ = 'report.generate'

    logger = logging.getLogger(__name__)

    @classmethod
    def __post_setup__(cls):
        super(ReportGenerate, cls).__post_setup__()
        if not config.get('bdoc', 'bdoc_web_wsdl'):
            cls.logger.warning('Configuration not found for bdoc wsdl')

    @classmethod
    def process_bdoc(cls, ids, data):
        wsdl_url = config.get('bdoc', 'bdoc_web_wsdl')
        report_template = Pool().get('report.template')(data['doc_template'][0])
        # Compute xml file
        extension, xml_file, d, filename = cls.process_shared_genshi_template(
            ids, data)
        if ServerContext().get('from_batch', None):
            return 'xmlstandard', xml_file, d, filename
        # Call BDOC generation web service
        client = Client(wsdl_url)
        # arg0: BDOC_template_domain of the report template;
        # arg1: Code of the report template;
        # arg2: User; arg4: Stream encoded in base 64;
        # arg6: BDOC Production format
        response = client.service.generation(
            report_template.BDOC_template_domain,
            report_template.code,
            '',
            '',
            xml_file,
            '',
            {'key': 'bwFormat', 'value': report_template.BDOC_production_format}
            )
        return (report_template.BDOC_production_format,
            response['documents'][0]['document'],
            False, filename)


class ReportTemplateVersion(metaclass=PoolMeta):
    __name__ = 'report.template.version'

    @fields.depends('template')
    def on_change_template(self):
        if self.template:
            self.is_shared_template = self.template.input_kind in [
                'shared_genshi_template', 'bdoc']
