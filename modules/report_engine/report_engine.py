# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
from decimal import Decimal, ROUND_HALF_UP
import sys
import zipfile
import traceback
import logging
import os
import subprocess
import shutil
import tempfile
import lxml.etree
try:
    from relatorio.templates.opendocument import Manifest, MANIFEST
except ImportError:
    Manifest, MANIFEST = None, None

from sql import Null, Literal
from datetime import datetime
from dateutil.relativedelta import relativedelta

from trytond import backend
from trytond.pool import Pool
from trytond.config import config
from trytond.model import Model, Unique
from trytond.wizard import Wizard, StateAction, StateView, Button
from trytond.wizard import StateTransition
from trytond.report import Report
from trytond.ir import Attachment
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from trytond.pyson import Eval, Equal
from trytond.model import DictSchemaMixin
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields, model, utils, coog_string, export

logger = logging.getLogger(__name__)

__all__ = [
    'TemplateParameter',
    'TemplateTemplateParameterRelation',
    'ReportTemplate',
    'ReportTemplateVersion',
    'Printable',
    'ReportGenerate',
    'ReportGenerateFromFile',
    'ReportCreate',
    'ReportCreateSelectTemplate',
    'ReportCreatePreview',
    'ReportCreatePreviewLine',
    ]

FILE_EXTENSIONS = [
    ('odt', 'Open Document Text (.odt)'),
    ('odp', 'Open Document Presentation (.odp)'),
    ('ods', 'Open Document Spreadsheet (.ods)'),
    ('odg', 'Open Document Graphics (.odg)'),
    ]


class TemplateParameter(DictSchemaMixin, model.CoogSQL, model.CoogView):
    'Template Parameter'

    __name__ = 'report.template.parameter'
    _func_key = 'name'

    @classmethod
    def __setup__(cls):
        super(TemplateParameter, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.name), 'The code must be unique'),
            ]
        cls._order.insert(0, ('name', 'ASC'))

    @property
    def name_in_template(self):
        return 'param_' + str(self.name)

    @classmethod
    def get_data_for_report(cls, parameters):
        return {'param_' + k: v for k, v in parameters.iteritems()}


class TemplateTemplateParameterRelation(model.CoogSQL):
    'Relation between Report Template and Template Parameter'

    __name__ = 'report.template-report.template.parameter'

    report_template = fields.Many2One('report.template', 'Template',
        ondelete='CASCADE')
    parameter = fields.Many2One('report.template.parameter', 'Parameter',
        ondelete='RESTRICT')


@model.genshi_evaluated_fields('export_dir')
class ReportTemplate(model.CoogSQL, model.CoogView, model.TaggedMixin):
    'Report Template'

    __name__ = 'report.template'
    _func_key = 'code'

    name = fields.Char('Name', required=True, translate=True)
    on_model = fields.Many2One('ir.model', 'Model',
        domain=[('printable', '=', True)], required=True, ondelete='RESTRICT')
    code = fields.Char('Code', required=True)
    versions = fields.One2Many('report.template.version', 'resource',
        'Versions', delete_missing=True)
    kind = fields.Selection('get_possible_kinds', 'Kind')
    output_kind = fields.Selection('get_possible_output_kinds',
        'Output kind', required=True)
    format_for_internal_edm = fields.Selection('get_available_formats',
        'Format for internal EDM',
        help="If no format is specified, the document will not be stored "
        "in the internal EDM")
    document_desc = fields.Many2One('document.description',
        'Document Description', ondelete='SET NULL')
    modifiable_before_printing = fields.Boolean('Modifiable',
        help='Set to true if you want to modify the generated document before '
        'sending or printing')
    template_extension = fields.Selection(FILE_EXTENSIONS,
        'Template Extension')
    export_dir = fields.Char('Export Directory', help='Store a copy of each '
        'generated document in specified server directory')
    convert_to_pdf = fields.Boolean('Convert to pdf', states={
            'invisible': Equal(Eval('output_method'), 'flat_document')},
        depends=['output_method'])
    split_reports = fields.Boolean('Split Reports', states={
            'invisible': Equal(Eval('output_method'), 'flat_document')},
        depends=['output_method'],
        help="If checked, one document will be produced for each object. "
        "If not checked a single document will be produced for several "
        "objects.")
    event_type_actions = fields.Many2Many('event.type.action-report.template',
            'report_template', 'event_type_action', 'Event Type Actions')
    parameters = fields.Many2Many('report.template-report.template.parameter',
        'report_template', 'parameter', 'Parameters')
    output_method = fields.Selection('get_possible_output_methods',
        'Output method', states={
            }, depends=['output_kind'])

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('code_unique', Unique(t, t.code),
                'The document template code must be unique'),
            ]
        cls._error_messages.update({
                'no_version_match': 'No letter model found for date %s '
                'and language %s',
                'output_method_open_document': 'Open Document',
                'output_method_flat_document': 'Flat Document',
                'output_kind_from_model': 'From File',
                'format_original': 'Original',
                'format_pdf': 'Pdf',
                'format_xlsx': 'xlsx',
                })

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.3: rename 'document_template' => 'report_template'
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        if TableHandler.table_exist('document_template'):
            TableHandler.table_rename('document_template',
                'report_template')
        report_template = TableHandler(cls)
        has_column_template_extension = report_template.column_exist(
            'template_extension')
        has_column_internal_edm = report_template.column_exist('internal_edm')
        has_column_output_kind = report_template.column_exist('output_kind')
        has_column_mail_subject = report_template.column_exist('mail_subject')
        has_column_mail_body = report_template.column_exist('mail_body')
        super(ReportTemplate, cls).__register__(module_name)
        to_update = cls.__table__()
        if not has_column_template_extension:
            # Migration from 1.4 : set default values for new columns
            cursor.execute("UPDATE report_template "
                "SET template_extension = 'odt' "
                "WHERE template_extension IS NULL")
            cursor.execute("UPDATE report_template SET convert_to_pdf = 'TRUE'"
                "WHERE convert_to_pdf IS NULL")
            cursor.execute("UPDATE report_template SET split_reports = 'TRUE'"
                "WHERE split_reports IS NULL")
        if has_column_internal_edm:
            # Migration from 1.4 : Store template format for internal edm
            cursor.execute("UPDATE report_template "
                "SET format_for_internal_edm = 'pdf' "
                "WHERE internal_edm = 'TRUE' and convert_to_pdf = 'TRUE'")
            cursor.execute("UPDATE report_template "
                "SET format_for_internal_edm = 'original' "
                "WHERE internal_edm = 'TRUE' and convert_to_pdf = 'FALSE'")
            report_template.drop_column('internal_edm')
        if not has_column_output_kind:
            cursor.execute(*to_update.update(columns=[to_update.output_kind],
                    values=[Literal(cls.default_output_kind())],
                    where=to_update.output_kind == Null))
        if has_column_mail_subject or has_column_mail_body:
            # Migration from 1.10: New module report_engine_email
            cursor.execute(*to_update.update(columns=[to_update.output_method],
                    values=[Literal(cls.default_output_method())],
                    where=to_update.output_method == ''))
        if has_column_mail_subject:
            # Migration from 1.10: New module report_engine_email
            report_template.drop_column('mail_subject')
        if has_column_mail_body:
            # Migration from 1.10: New module report_engine_email
            report_template.drop_column('mail_body')

        # Migration from 1.10: Replace support from xls to xlsx
        cursor.execute(*to_update.update(
            columns=[to_update.format_for_internal_edm],
            values=['xlsx'],
            where=to_update.format_for_internal_edm == 'xls95'))

    @classmethod
    def copy(cls, reports, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('event_type_actions', None)
        return super(ReportTemplate, cls).copy(reports, default=default)

    @classmethod
    def default_output_method(cls):
        return 'open_document'

    @fields.depends('output_kind')
    def get_possible_output_methods(self):
        return [('open_document',
                self.raise_user_error('output_method_open_document',
                    raise_exception=False)),
            ('flat_document',
                self.raise_user_error('output_method_flat_document',
                    raise_exception=False))]

    @fields.depends('output_method')
    def get_available_formats(self):
        available_format = [
            ('', ''),
            ]
        if self.output_method == 'open_document':
            available_format += [
                ('original', self.__class__.raise_user_error(
                        'format_original', raise_exception=False)),
                ('pdf', self.__class__.raise_user_error(
                        'format_pdf', raise_exception=False)),
                ('xlsx', self.__class__.raise_user_error(
                        'format_xlsx', raise_exception=False)),
            ]
        elif self.output_method == 'flat_document':
            available_format += [
                ('original', self.__class__.raise_user_error(
                        'format_original', raise_exception=False)),
                ]
        return available_format

    @classmethod
    def search(cls, domain, *args, **kwargs):
        # Never search any document for which the user is not allowed to view
        # the type
        document_descs = Pool().get('document.description').search([])
        if document_descs:
            domain = ['AND', domain,
                ['OR', ('document_desc', '=', None),
                    ('document_desc', 'in', [x.id for x in document_descs])]]
        else:
            domain = ['AND', domain, [('document_desc', '=', None)]]
        return super(ReportTemplate, cls).search(domain, *args, **kwargs)

    @classmethod
    def default_output_kind(cls):
        return 'model'

    @classmethod
    def get_possible_output_kinds(cls):
        return [
            ('model', cls.raise_user_error('output_kind_from_model',
                    raise_exception=False))]

    @classmethod
    def _export_light(cls):
        return super(ReportTemplate, cls)._export_light() | {'products',
            'document_desc', 'on_model'}

    @classmethod
    def _export_skips(cls):
        return super(ReportTemplate, cls)._export_skips() | {
            'event_type_actions'}

    @classmethod
    def default_convert_to_pdf(cls):
        return True

    @classmethod
    def default_template_extension(cls):
        return 'odt'

    @classmethod
    def default_split_reports(cls):
        return True

    def get_selected_version(self, date, language):
        versions = [v for v in self.versions
            if (not v.start_date or v.start_date <= date)
            and (not v.end_date or v.end_date > date)]
        languages = [v.language.code for v in versions]
        if len(languages) > 1:
            if language not in languages:
                language = Transaction().language
            version_lang = [v for v in versions if v.language.code == language]
            if version_lang:
                return version_lang[0]
        if versions:
            return versions[0]
        self.raise_user_error('no_version_match', (date, language))

    def on_change_output_kind(self):
        pass

    @fields.depends('output_method', 'format_for_internal_edm')
    def on_change_output_method(self):
        if self.output_method == 'flat_document':
            self.format_for_internal_edm = 'original'
            self.convert_to_pdf = False

    @fields.depends('on_model')
    def get_possible_kinds(self):
        return [('', '')]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    def print_reports(self, reports, context_):
        """ Reports is a list of dicts with keys:
            object, origin, report type, data, report name"""
        if self.export_dir:
            ReportGenerate = Pool().get('report.generate', type='report')
            data = context_['reporting_data']
            records = ReportGenerate._get_records(data['ids'], data['model'],
                data)
            with ServerContext().set_context(
                    genshi_context=ReportGenerate.get_context(records, data)):
                self.export_reports(reports)

    def get_export_dirname(self):
        export_root_dir = config.get('report', 'export_root_dir')
        if not export_root_dir:
            raise Exception('Error', "No 'export_root_dir' configuration "
                'setting specified.')
        # authorize entering dirpath starting with '/' relative to the root
        export_dirname = os.path.realpath(os.path.join(export_root_dir,
            self.genshi_evaluated_export_dir.lstrip(os.sep)))
        # prevent user entering '..' to escape from root
        if not export_dirname.startswith(os.path.realpath(export_root_dir)):
            raise Exception('Error', ('Export directory outside of configured '
                'root directory'))
        if not os.path.exists(export_dirname):
            os.makedirs(export_dirname)
        return export_dirname

    def export_reports(self, reports, add_time=True):
        export_dirname = self.get_export_dirname()
        for report in reports:
            filename, ext = os.path.splitext(report['report_name'])
            filename = coog_string.slugify(filename)
            if add_time:
                filename += '_' + datetime.now().strftime("%H%M%S%f")
            filename += ext
            out_path = os.path.join(export_dirname, filename)
            with open(out_path, 'a') as out:
                out.write(report['data'])

    def _create_attachment_from_report(self, report):
        """ Report is a dictionary with:
            object_instance, report type, data, report name"""

        pool = Pool()
        Attachment = pool.get('ir.attachment')
        attachment = Attachment()
        attachment.resource = report['resource'] or \
            report['object'].get_reference_object_for_edm(self)
        attachment.data = report['data']
        attachment.name = report['report_name']
        attachment.document_desc = self.document_desc
        attachment.origin = report.get('origin', None)
        return attachment

    def save_reports_in_edm(self, reports):
        """ Reports is a list of dictionnary with:
            object_instance, report type, data, report name"""
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        attachments = []
        for report in reports:
            attachments.append(self._create_attachment_from_report(report))
        Attachment.save(attachments)
        return attachments

    def _generate_report(self, objects, context_):
        pool = Pool()
        ReportModel = pool.get('report.generate', type='report')
        objects_ids = [x.id for x in objects]
        reporting_data = {
                'id': objects_ids[0],
                'ids': objects_ids,
                'model': objects[0].__name__,
                'doc_template': [self],
                'party': objects[0].get_contact(),
                'address': objects[0].get_address(),
                'sender': objects[0].get_sender(),
                'sender_address': objects[0].get_sender_address(),
                'origin': None,
                }
        reporting_data.update(context_)
        context_['reporting_data'] = reporting_data
        if self.parameters:
            reporting_data.update({x.name_in_template: None
                    for x in self.parameters})
        functional_date = context_.get('functional_date')
        if functional_date and functional_date != utils.today():
            with Transaction().set_context(
                    client_defined_date=functional_date):
                extension, data, _, report_name = ReportModel.execute(
                    objects_ids, reporting_data, immediate_conversion=True)
        else:
            extension, data, _, report_name = ReportModel.execute(
                objects_ids, reporting_data, immediate_conversion=True)
        return {
                'object': objects[0],
                'report_type': extension,
                'data': data,
                'report_name': '%s.%s' % (report_name, extension),
                'origin': context_.get('origin', None),
                'resource': context_.get('resource', None),
                }

    def _generate_reports(self, objects, context_):
        """ Return a list of dictionnary with:
            object, report_type, data, report_name"""
        if not objects:
            return []
        reports = []
        if self.split_reports:
            for _object in objects:
                reports.append(
                    self._generate_report([_object], context_))
        else:
            reports.append(self._generate_report(objects, context_))
        return reports

    def produce_reports(self, objects, context_=None):
        if context_ is None:
            context_ = {}
        reports = self._generate_reports(objects, context_)
        self.print_reports(reports, context_)
        attachments = []
        if self.format_for_internal_edm:
            attachments = self.save_reports_in_edm(reports)
        return reports, attachments

    @classmethod
    def find_templates_for_objects_and_kind(cls, objects, model_name, kind):
        """ Return a dictionnary with template instance as key
        and a list of objects as value"""
        pool = Pool()
        Model = pool.get('ir.model')
        model, = Model.search([('model', '=', model_name)])
        templates = cls.search([('kind', '=', kind),
                ('on_model', '=', model.id)])
        res = {}
        for template in templates:
            res[template] = objects
        return res

    def get_style_content(self, at_date, _object):
        style_method = getattr(_object, 'get_report_style_content', None)
        if style_method:
            return style_method(at_date, self)


class ReportTemplateVersion(Attachment, export.ExportImportMixin):
    'Report Template Version'

    __name__ = 'report.template.version'
    _table = None

    start_date = fields.Date('Start date', required=True)
    end_date = fields.Date('End date')
    language = fields.Many2One('ir.lang', 'Language', required=True,
        ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.3: rename 'document_template' => 'report_template'
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        if TableHandler.table_exist('document_template_version'):
            TableHandler.table_rename(
                'document_template_version', 'report_template_version')
            cursor.execute("UPDATE report_template_version "
                "SET resource = REPLACE(resource, 'document.', 'report.')")
        super(ReportTemplateVersion, cls).__register__(module_name)

    @classmethod
    def __setup__(cls):
        super(ReportTemplateVersion, cls).__setup__()
        cls.type.states = {'readonly': True}
        cls.resource.selection = [('report.template', 'Document Template')]
        cls.resource.required = True
        cls._export_binary_fields.add('data')

    @classmethod
    def default_type(cls):
        return 'data'

    @classmethod
    def _export_light(cls):
        return (super(ReportTemplateVersion, cls)._export_light() |
            set(['resource', 'language']))

    @classmethod
    def _export_skips(cls):
        return (super(ReportTemplateVersion, cls)._export_skips() |
            set(['digest', 'collision']))


class Printable(Model):
    'Base class for printable objects'
    @classmethod
    def __register__(cls, module_name):
        # We need to store the fact that this class is a Printable class in the
        # database.
        super(Printable, cls).__register__(module_name)
        GoodModel = Pool().get('ir.model')
        good_model, = GoodModel.search([
            ('model', '=', cls.__name__)], limit=1)
        good_model.printable = True
        good_model.save()

    @classmethod
    @model.CoogView.button_action('report_engine.letter_generation_wizard')
    def generic_send_letter(cls, objs):
        pass

    def get_contact(self):
        raise NotImplementedError

    def get_recipients(self):
        return [self.get_contact()]

    def get_lang(self):
        try:
            return self.get_contact().lang.code
        except:
            return Transaction().language

    def get_address(self):
        contact = self.get_contact()
        if not contact:
            return ''
        address = contact.addresses[0] if contact.addresses else None
        return address

    def get_available_doc_templates(self, kind=None):
        DocumentTemplate = Pool().get('report.template')

        if kind:
            domain_kind = ('kind', '=', kind)
        else:
            domain_kind = ('kind', 'in', self.get_doc_template_kind())

        domain = self.build_template_domain(domain_kind)
        if not domain:
            domain = [
                ('on_model.model', '=', self.__name__),
                ]
        return DocumentTemplate.search(domain)

    def build_template_domain(self, domain_kind):
        template_holders_sub_domains = self.get_template_holders_sub_domains()
        if not template_holders_sub_domains:
            return
        return [
            ('on_model.model', '=', self.__name__),
            ['OR'] + template_holders_sub_domains,
            ['OR', domain_kind, ('kind', '=', '')]
            ]

    def get_template_holders_sub_domains(self):
        return []

    def get_doc_template_kind(self):
        return ['']

    def get_reference_object_for_edm(self, template):
        return self

    def post_generation(self):
        pass

    def get_object_for_contact(self):
        return self

    def get_appliable_logo(self, kind=''):
        sender = self.get_sender()
        if not sender or not sender.logo:
            return ''
        return sender.logo

    def format_logo(self):
        good_logo = self.get_appliable_logo()
        if not good_logo:
            return ''
        return StringIO.StringIO(str(good_logo))

    def get_sender(self):
        return self.get_object_for_contact().get_sender()

    def get_sender_address(self):
        sender = self.get_sender()
        if not sender or not sender.addresses:
            return None
        return sender.addresses[0]

    def get_product(self):
        raise NotImplementedError

    def get_publishing_context(self, cur_context):
        return {
            'Today': datetime.now().date(),
            }

    def get_report_functional_date(self, event_code):
        return utils.today()

    def get_document_filename(self):
        return self.rec_name

    @classmethod
    def produce_reports(cls, objects, template_kind, context_=None):
        all_reports, all_attachments = [], []
        pool = Pool()
        Template = pool.get('report.template')
        if not template_kind:
            return
        templates = Template.find_templates_for_objects_and_kind(objects,
            cls.__name__, template_kind)
        for template, group_objects in templates.iteritems():
            reports, attachments = template.produce_reports(objects, context_)
            all_reports.extend(reports)
            all_attachments.extend(attachments)
        return all_reports, all_attachments


class ReportGenerate(Report):
    __name__ = 'report.generate'

    @classmethod
    def process_flat_document(cls, ids, data, immediate_conversion):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        action_reports = ActionReport.search([
                ('report_name', '=', cls.__name__)
                ])
        SelectedModel = Pool().get(data['model'])
        selected_obj = SelectedModel(data['id'])
        selected_letter = Pool().get('report.template')(
            data['doc_template'][0])
        version = selected_letter.get_selected_version(utils.today(),
            selected_obj.get_lang())
        extension = os.path.splitext(version.name)[1][1:]
        name_giver = data.get('resource', None) or SelectedModel(data['id'])
        selected_party = pool.get('party.party')(data['party'])
        filename = cls.get_filename(selected_letter, name_giver,
            selected_party)
        return (extension, version.data, action_reports[0].direct_print,
            filename)

    @classmethod
    def process_open_document(cls, ids, data, immediate_conversion):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        action_reports = ActionReport.search([
                ('report_name', '=', cls.__name__)
                ])
        if not action_reports:
            raise Exception('Error', 'Report (%s) not find!' % cls.__name__)
        action_report = action_reports[0]
        records = None
        records = cls._get_records(ids, data['model'], data)
        selected_letter = Pool().get('report.template')(
            data['doc_template'][0])
        SelectedModel = pool.get(data['model'])
        name_giver = data.get('resource', None) or SelectedModel(data['id'])
        selected_party = pool.get('party.party')(data['party'])
        filename = cls.get_filename(selected_letter, name_giver,
            selected_party)
        report_context = cls.get_context(records, data)
        action_report.template_extension = selected_letter.template_extension
        # ABD: We should consider convert_to_pdf
        # event if format_for_internal_edm is not set
        if immediate_conversion and selected_letter.format_for_internal_edm \
                not in ('', 'original'):
            action_report.extension = selected_letter.format_for_internal_edm
        elif selected_letter.convert_to_pdf:
            action_report.extension = 'pdf'
        oext, content = cls.convert(action_report,
            cls.render(action_report, report_context))
        return (oext, bytearray(content), action_report.direct_print, filename)

    @classmethod
    def execute(cls, ids, data, immediate_conversion=False):
        report_template = Pool().get('report.template')(
            data['doc_template'][0])
        method_name = 'process_%s' % report_template.output_method
        records = cls._get_records(ids, data['model'], data)
        report_context = cls.get_context(records, data)
        with ServerContext().set_context(genshi_context=report_context):
            if hasattr(cls, method_name):
                return getattr(cls, method_name)(ids, data,
                    immediate_conversion=immediate_conversion)
            else:
                raise NotImplementedError('Unknown kind %s' %
                    report_template.output_method)

    @classmethod
    def get_filename_separator(cls):
        return '-'

    @classmethod
    def get_date_suffix(cls, language):
        pool = Pool()
        Date = pool.get('ir.date')
        return coog_string.slugify(
            Date.date_as_string(utils.today(), language))

    @classmethod
    def get_time_suffix(cls):
        return datetime.utcnow().strftime('%X')

    @classmethod
    def get_filename(cls, template, object_, party):
        separator = cls.get_filename_separator()
        date_suffix = cls.get_date_suffix(party.lang)
        time_suffix = cls.get_time_suffix()
        return separator.join([x for x in [template.name, object_.rec_name,
                    date_suffix, time_suffix] if x])

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ReportGenerate, cls).get_context(
            records, data)
        pool = Pool()
        report_context['Decimal'] = Decimal

        def custom_round(amount, number):
            if isinstance(amount, Decimal):
                return amount.quantize(Decimal(10) ** -number,
                    rounding=ROUND_HALF_UP)
            else:
                return round(amount, number)

        report_context['round'] = custom_round
        report_context['Party'] = pool.get('party.party')(data['party'])
        report_context['Address'] = pool.get('party.address')(data['address'])
        try:
            report_context['Lang'] = report_context['Party'].lang.code
        except AttributeError:
            report_context['Lang'] = pool.get('ir.lang').search([
                    ('code', '=', 'en')])[0]
        if data['sender']:
            report_context['Sender'] = pool.get('party.party')(data['sender'])
        else:
            report_context['Sender'] = None
        if data['sender_address']:
            report_context['SenderAddress'] = pool.get(
                'party.address')(data['sender_address'])
        else:
            report_context['SenderAddress'] = None

        def format_date(value, lang=None):
            if lang is None:
                lang = report_context['Party'].lang
            return pool.get('ir.lang').strftime(value, lang.code, lang.date)

        report_context.update({k: v for k, v in data.iteritems() if k not in
                ['party', 'address', 'sender', 'sender_address']})

        report_context['Date'] = pool.get('ir.date').today()
        report_context['FDate'] = format_date
        report_context['relativedelta'] = relativedelta
        report_context['Company'] = pool.get('party.party')(
            Transaction().context.get('company'))
        SelectedModel = pool.get(data['model'])
        selected_obj = SelectedModel(data['id'])
        report_context.update(selected_obj.get_publishing_context(
                report_context))
        return report_context

    @classmethod
    def render(cls, report, report_context):
        pool = Pool()
        SelectedModel = pool.get(report_context['data']['model'])
        selected_obj = SelectedModel(report_context['data']['id'])
        selected_letter = Pool().get('report.template')(
            report_context['data']['doc_template'][0])
        report.report_content = selected_letter.get_selected_version(
            utils.today(), selected_obj.get_lang()).data
        report.style_content = selected_letter.get_style_content(
            utils.today(), selected_obj)

        try:
            return super(ReportGenerate, cls).render(
                report, report_context)
        except Exception, exc:
            # Try to extract the relevant information to display to the user.
            # That would be the part of the genshi template being evaluated and
            # the "final" error. In case anything goes wrong, raise the
            # original error
            try:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                tmp = traceback.extract_tb(exc_traceback)
                for frame in reversed(tmp):
                    if (frame[0] != '<string>' and not
                            frame[0].endswith('.odt')):
                        continue
                    ReportCreate = pool.get('report.create', type='wizard')
                    ReportCreate.raise_user_error('parsing_error', (
                            frame[2][14:-2], str(exc)))
                else:
                    raise exc
            except UserError:
                raise
            except:
                pass
            raise exc

    @classmethod
    def create_shared_tmp_dir(cls):
        server_shared_folder = config.get('EDM', 'server_shared_folder',
            default='/tmp')
        client_shared_folder = config.get('EDM', 'client_shared_folder')
        try:
            tmp_dir = os.path.basename(
                tempfile.mkdtemp(dir=server_shared_folder))
        except OSError as e:
            raise Exception('Could not create tmp_directory in %s (%s)' %
                (server_shared_folder, e))
        server_filepath = os.path.join(server_shared_folder, tmp_dir)
        client_filepath = os.path.join(client_shared_folder, tmp_dir) \
            if client_shared_folder else ''
        return client_filepath, server_filepath

    @classmethod
    def edm_write_tmp_report(cls, report_data, filename):
        basename, ext = os.path.splitext(filename)
        filename = coog_string.slugify(basename, lower=False) + ext
        client_filepath, server_filepath = cls.create_shared_tmp_dir()
        client_filepath = os.path.join(client_filepath, filename)
        server_filepath = os.path.join(server_filepath, filename)
        with open(server_filepath, 'w') as f:
            f.write(report_data)
            return(client_filepath, server_filepath)

    @classmethod
    def _prepare_template_file(cls, report):
        '''
        Override the trytond method in order to apply template style
        if style_content defined in report
        '''
        # Convert to str as value from DB is not supported by StringIO

        style_content = getattr(report, 'style_content', None)
        if not style_content:
            return super(ReportGenerate, cls)._prepare_template_file(report)

        report_content = (bytes(report.report_content) if report.report_content
            else None)
        if not report_content:
            raise Exception('Error', 'Missing report file!')

        style_content = bytes(style_content)

        fd, path = tempfile.mkstemp(
            suffix=(os.extsep + report.template_extension),
            prefix='trytond_')
        outzip = zipfile.ZipFile(path, mode='w')

        content_io = StringIO.StringIO()
        content_io.write(report_content)
        content_z = zipfile.ZipFile(content_io, mode='r')

        style_info = None
        style_xml = None
        manifest = None
        for f in content_z.infolist():
            if f.filename == 'styles.xml' and style_content:
                style_info = f
                style_xml = content_z.read(f.filename)
                continue
            elif Manifest and f.filename == MANIFEST:
                manifest = Manifest(content_z.read(f.filename))
                continue
            outzip.writestr(f, content_z.read(f.filename))

        if style_content:
            pictures = []

            # cStringIO difference:
            # calling StringIO() with a string parameter creates a read-only
            # object
            new_style_io = StringIO.StringIO()
            new_style_io.write(style_content)
            new_style_z = zipfile.ZipFile(new_style_io, mode='r')
            new_style_xml = new_style_z.read('styles.xml')
            for file in new_style_z.namelist():
                if file.startswith('Pictures'):
                    picture = new_style_z.read(file)
                    pictures.append((file, picture))
                    if manifest:
                        manifest.add_file_entry(file)
            new_style_z.close()
            new_style_io.close()

            style_tree = lxml.etree.parse(StringIO.StringIO(style_xml))
            style_root = style_tree.getroot()

            new_style_tree = lxml.etree.parse(StringIO.StringIO(new_style_xml))
            new_style_root = new_style_tree.getroot()

            for style in ('master-styles', 'automatic-styles', 'styles'):
                node, = style_tree.xpath(
                        '/office:document-styles/office:%s' % style,
                        namespaces=style_root.nsmap)
                new_node, = new_style_tree.xpath(
                        '/office:document-styles/office:%s' % style,
                        namespaces=new_style_root.nsmap)
                node.getparent().replace(node, new_node)

            outzip.writestr(style_info,
                    lxml.etree.tostring(style_tree, encoding='utf-8',
                        xml_declaration=True))

            for file, picture in pictures:
                outzip.writestr(file, picture)

        if manifest:
            outzip.writestr(MANIFEST, bytes(manifest))

        content_z.close()
        content_io.close()
        outzip.close()
        return fd, path


class ReportGenerateFromFile(Report):
    __name__ = 'report.generate_from_file'

    @classmethod
    def execute(cls, ids, data):
        with open(data['output_report_filepath'], 'r') as f:
            value = bytearray(f.read())
        return (data['output_report_filepath'].split('.')[-1], value, False,
            os.path.splitext(
                os.path.basename(data['output_report_filepath']))[0])

    @classmethod
    def convert_single_attachment(cls, input_paths, output_report_filepath):
        pdf_paths = cls.unoconv(input_paths, 'odt', 'pdf')
        if len(pdf_paths) > 1:
            if os.path.splitext(output_report_filepath)[1] == '.pdf':
                cmd = ['gs', '-dBATCH', '-dNOPAUSE', '-q', '-sDEVICE=pdfwrite',
                    '-sOutputFile=%s' % output_report_filepath] + pdf_paths
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                stdoutdata, stderrdata = proc.communicate()
                if proc.wait() != 0:
                    raise Exception(stderrdata)
            # TODO: handle 'zip' format for grouping of mixed files formats
        else:
            shutil.move(pdf_paths[0], output_report_filepath)

    @classmethod
    def unoconv(cls, filepaths, input_format, output_format):
        from trytond.report import FORMAT2EXT
        oext = FORMAT2EXT.get(output_format, output_format)
        cmd = ['unoconv', '--no-launch', '--connection=%s' % config.get(
                'report', 'unoconv'), '-f', oext] + filepaths
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True)
        stdoutdata, stderrdata = proc.communicate()
        if proc.returncode != 0:
            logger.error('unoconv.stdout : ' + stdoutdata)
            logger.error('unoconv.errorcode: ' + str(proc.returncode))
            logger.error('unoconv.stderr : ' + stderrdata)
            raise Exception(stderrdata)
        else:
            logger.debug('unoconv.stdout : ' + stdoutdata)
            logger.debug('unoconv.stderr : ' + stderrdata)
        output_paths = [os.path.splitext(f)[0] + '.' + output_format for
            f in filepaths]
        return output_paths


class ReportCreate(Wizard):
    'Report Creation'

    __name__ = 'report.create'

    start_state = 'init_templates'
    init_templates = StateTransition()
    select_template = StateView('report.create.select_template',
        'report_engine.create_report_select_template_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate', 'generate', 'tryton-go-next', default=True)])
    generate = StateTransition()
    preview_document = StateView('report.create.preview',
        'report_engine.document_create_preview_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'select_template', 'tryton-go-previous'),
            Button('Open', 'open_document', 'tryton-print-open')
            ])
    open_document = StateAction('report_engine.generate_file_report')
    post_generation = StateTransition()
    attach_to_contact = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ReportCreate, cls).__setup__()
        cls._error_messages.update({
                'parsing_error': 'Error while generating the letter:\n\n'
                '  Expression:\n%s\n\n  Error:\n%s',
                'contact_not_provided': 'Report is impossible: '
                'No contact available.',
                })

    def get_instance(self):
        transaction = Transaction()
        ActiveModel = Pool().get(transaction.context.get('active_model'))
        return ActiveModel(transaction.context.get('active_id'))

    def transition_init_templates(self):
        instance = self.get_instance()
        kind = Transaction().context.get('report_kind', None)
        possible_templates = instance.get_available_doc_templates(kind)
        self.select_template.possible_templates = possible_templates
        if len(self.select_template.possible_templates) == 1:
            self.select_template.template = possible_templates[0]
        possible_recipients = instance.get_recipients()
        if not possible_recipients:
            self.raise_user_error('contact_not_provided')
        self.select_template.possible_recipients = possible_recipients
        self.select_template.recipient = possible_recipients[0]
        return 'select_template'

    def default_select_template(self, fields):
        return self.select_template._default_values

    def create_report_context(self):
        instance = self.get_instance()
        template = self.select_template.template
        sender = instance.get_sender()
        sender_address = instance.get_sender_address()
        return {
            'id': instance.id,
            'ids': [instance.id],
            'model': instance.__name__,
            'doc_template': [template.id],
            'party': self.select_template.recipient.id,
            'address': self.select_template.recipient_address.id
            if self.select_template.recipient_address else None,
            'sender': sender.id if sender else None,
            'sender_address': sender_address.id if sender_address else None,
            'origin': None,
            }

    def transition_generate(self):
        self.remove_edm_temp_files()
        instance = self.get_instance()
        report_context = self.create_report_context()
        pool = Pool()
        TemplateParameter = pool.get('report.template.parameter')
        template = self.select_template.template
        if self.select_template.parameters:
            report_context.update(TemplateParameter.get_data_for_report(
                    self.input_parameters.parameters))
        report = self.report_execute([instance.id], template, report_context)
        self.finalize_report(report, instance)
        if self.select_template.template.modifiable_before_printing:
            return 'preview_document'
        return 'open_document'

    def remove_edm_temp_files(self):
        try:
            for f in self.preview_document.reports:
                shutil.rmtree(os.path.dirname(f.server_filepath))
        except (AttributeError, OSError):
            # no reports or report already removed
            pass

    def report_execute(self, ids, doc_template, report_context):
        ReportModel = Pool().get('report.generate', type='report')
        ext, filedata, prnt, file_basename = ReportModel.execute(ids,
            report_context, immediate_conversion=(
                not doc_template.convert_to_pdf and
                not doc_template.modifiable_before_printing))
        client_filepath, server_filepath = ReportModel.edm_write_tmp_report(
            filedata, '%s.%s' % (file_basename, ext))
        return {
            'generated_report': client_filepath,
            'server_filepath': server_filepath,
            'file_basename': file_basename,
            'template': doc_template,
            }

    def finalize_report(self, report, instance):
        self.preview_document.reports = [report]
        output = instance.get_document_filename()
        self.preview_document.output_report_name = coog_string.slugify(output,
            lower=False)
        self.preview_document.output_report_filepath = \
            self.preview_document.on_change_with_output_report_filepath()
        self.preview_document.recipient = self.select_template.recipient.id

    def default_preview_document(self, fields):
        return self.preview_document._default_values

    def do_open_document(self, action):
        return self.action_open_report(action,
            Transaction().context.get('email_print'))

    def transition_open_document(self):
        if not self.select_template.template.format_for_internal_edm:
            return 'end'
        return 'post_generation'

    def action_open_report(self, action, email_print):
        pool = Pool()
        Report = pool.get('report.generate_from_file', type='report')
        if (self.select_template.template.convert_to_pdf and not
                self.preview_document.reports[0].server_filepath.endswith(
                    '.pdf')):
            Report.convert_single_attachment(
                [self.preview_document.reports[0].server_filepath],
                self.preview_document.output_report_filepath)
            filename = self.preview_document.output_report_filepath
        else:
            filename = [self.preview_document.reports[0].server_filepath][0]
        action['email_print'] = email_print
        action['direct_print'] = Transaction().context.get('direct_print')
        action['email'] = {'to': ''}
        return action, {'output_report_filepath': filename}

    def transition_post_generation(self):
        instance = self.get_instance()
        instance.post_generation()
        contact = self.set_contact()
        contact.save()
        attachment = self.set_attachment(
            contact.for_object_ref or contact.party)
        attachment.save()
        return 'end'

    def set_contact(self):
        ContactHistory = Pool().get('party.interaction')
        contact = ContactHistory()
        contact.party = self.select_template.recipient
        contact.media = 'mail'
        contact.address = self.select_template.recipient_address
        contact.title = self.select_template.template.name
        contact.for_object_ref = self.get_instance().get_object_for_contact()
        return contact

    def set_attachment(self, resource):
        if self.select_template.template.format_for_internal_edm == 'original':
            file_name = self.preview_document.reports[0].server_filepath
        else:
            file_name = self.preview_document.output_report_filepath
        Attachment = Pool().get('ir.attachment')
        attachment = Attachment()
        attachment.resource = resource
        with open(file_name, 'r') as f:
            attachment.data = bytearray(f.read())
        attachment.name = os.path.basename(file_name)
        attachment.document_desc = self.select_template.template.document_desc
        return attachment


class ReportCreateSelectTemplate(model.CoogView):
    'Report Creation Select Template'

    __name__ = 'report.create.select_template'

    template = fields.Many2One('report.template', 'Template', required=True,
        domain=[('id', 'in', Eval('possible_templates'))],
        depends=['possible_templates'])
    possible_templates = fields.Many2Many('report.template', None, None,
        'Possible Templates', states={'invisible': True})
    recipient = fields.Many2One('party.party', 'Recipient', required=True,
        states={'invisible': ~Eval('template')},
        domain=[('id', 'in', Eval('possible_recipients'))],
        depends=['possible_recipients'])
    possible_recipients = fields.Many2Many('party.party', None, None,
        'Possible Recipients', states={'invisible': True})
    recipient_address = fields.Many2One('party.address', 'Recipient Address',
        domain=[('party', '=', Eval('recipient'))], states={
            'invisible': ~Eval('recipient') | ~Eval('template')},
        depends=['recipient', 'template'])
    parameters = fields.Dict('report.template.parameters', 'Parameters',
        states={'invisible': ~Eval('parameters')}, depends=['parameters'])

    @fields.depends('parameters', 'recipient', 'recipient_address', 'template')
    def on_change_template(self):
        if not self.template:
            self.recipient = None
            self.on_change_recipient()
            self.parameters = {}
        else:
            self.parameters = {
                str(x.name): None for x in self.template.parameters}

    @fields.depends('recipient', 'recipient_address')
    def on_change_recipient(self):
        if not self.recipient:
            self.recipient_address = None
        else:
            self.recipient_address = self.recipient.address_get()


class ReportCreatePreview(model.CoogView):
    'Report Create Preview'

    __name__ = 'report.create.preview'

    reports = fields.One2Many('report.create.preview.line', None,
        'Reports', states={'readonly': True})
    output_report_name = fields.Char('Output Report Name')
    output_report_filepath = fields.Char('Output Report Filepath',
        states={'invisible': True})

    @fields.depends('output_report_name', 'reports')
    def on_change_with_output_report_filepath(self, name=None):
        if all([x.template.convert_to_pdf and not os.path.isfile(
                        x.server_filepath) for x in self.reports]):
            # Generate unique temporary output report filepath
            return os.path.join(tempfile.mkdtemp(), coog_string.slugify(
                        self.output_report_name, lower=False) + '.pdf')
        else:
            return self.reports[0].server_filepath


class ReportCreatePreviewLine(model.CoogView):
    'Report Create Preview Line'

    __name__ = 'report.create.preview.line'

    template = fields.Many2One('report.template', 'Template')
    generated_report = fields.Char('Link')
    server_filepath = fields.Char('Server Filename',
        states={'invisible': True})
    file_basename = fields.Char('Filename')
