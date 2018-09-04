# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
from decimal import Decimal, ROUND_HALF_UP
import stat
import sys
import zipfile
import traceback
import logging
import os
import subprocess
import shutil
import tempfile
import lxml.etree
import base64
try:
    from relatorio.templates.opendocument import Manifest, MANIFEST
except ImportError:
    Manifest, MANIFEST = None, None

from itertools import groupby, chain
from sql import Cast, Null, Literal
from sql.functions import Substring, Position
from datetime import datetime
from dateutil.relativedelta import relativedelta

from trytond import backend
from trytond.pool import Pool, PoolMeta
from trytond.config import config
from trytond.model import Model, Unique
from trytond.wizard import StateAction, StateView, Button
from trytond.wizard import StateTransition
from trytond.report import Report
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from trytond.pyson import Eval, Equal, Bool
from trytond.model import DictSchemaMixin
from trytond.server_context import ServerContext
from trytond.filestore import filestore
from trytond.tools import file_open
from trytond.rpc import RPC

from trytond.modules.coog_core import fields, model, utils, coog_string
from trytond.modules.coog_core import wizard_context, coog_date

logger = logging.getLogger(__name__)

__all__ = [
    'TemplateParameter',
    'TemplateTemplateParameterRelation',
    'ReportTemplate',
    'ReportLightTemplate',
    'ReportTemplateVersion',
    'ReportTemplateGroupRelation',
    'Printable',
    'CoogReport',
    'ReportGenerate',
    'ReportGenerateFromFile',
    'ReportCreate',
    'ReportCreateSelectTemplate',
    'ReportCreatePreview',
    'ReportCreatePreviewLine',
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


@model.genshi_evaluated_fields('export_dir', 'output_filename')
class ReportTemplate(model.CoogSQL, model.CoogView, model.TaggedMixin):
    'Report Template'

    __name__ = 'report.template'
    _func_key = 'code'

    name = fields.Char('Name', required=True, translate=True)
    on_model = fields.Many2One('ir.model', 'Model',
        domain=[('printable', '=', True)], ondelete='RESTRICT')
    code = fields.Char('Code', required=True)
    versions = fields.One2Many('report.template.version', 'template',
        'Versions', delete_missing=True)
    kind = fields.Selection('get_possible_kinds', 'Kind')
    input_kind = fields.Selection('get_possible_input_kinds',
        'Input Kind', required=True)
    format_for_internal_edm = fields.Selection('get_available_formats',
        'Format for internal EDM',
        help="If no format is specified, the document will not be stored "
        "in the internal EDM")
    output_format = fields.Selection([('', ''),
        ('libre_office', 'Libre Office'), ('pdf', 'Pdf'),
        ('microsoft_office', 'Microsoft Office')],
        'Output Format', states={
            'required': Eval('process_method') == 'libre_office',
            'invisible': Eval('process_method') != 'libre_office',
        })
    # Do not remove required: False in state.
    # It is required to avoid checks in children modules
    output_filename = fields.Char('Output Filename',
        states={'required': False})
    document_desc = fields.Many2One('document.description',
        'Document Description', ondelete='SET NULL')
    modifiable_before_printing = fields.Boolean('Modifiable',
        help='Set to true if you want to modify the generated document before '
        'sending or printing')
    export_dir = fields.Char('Export Directory', help='Store a copy of each '
        'generated document in specified server directory')
    split_reports = fields.Boolean('Split Reports', states={
            'invisible': Equal(Eval('process_method'), 'flat_document')},
        depends=['process_method'],
        help="If checked, one document will be produced for each object. "
        "If not checked a single document will be produced for several "
        "objects.")
    event_type_actions = fields.Many2Many('event.type.action-report.template',
            'report_template', 'event_type_action', 'Event Type Actions')
    parameters = fields.Many2Many('report.template-report.template.parameter',
        'report_template', 'parameter', 'Parameters')
    process_method = fields.Selection('get_possible_process_methods',
        'Process Method', states={
            'invisible': Eval('nb_of_possible_process_methods', 0) <= 1
            }, depends=['input_kind', 'nb_of_possible_process_methods'])
    nb_of_possible_process_methods = fields.Function(
        fields.Integer('Number of possible process methods',),
        'on_change_with_nb_of_possible_process_methods')
    recipient_needed = fields.Boolean('Recipient Needed',
        help='If True, the recipient will be required when printing the '
        'document. This will make simultaneous printing impossible for this '
        'model.')
    groups = fields.Many2Many(
        'report.template-res.group', 'report_template',
        'group', 'Groups',
        help='If the user belongs to one of the groups linked to the report '
        'template, he can see it in the report wizard.')

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        cls.__rpc__.update({
                'produce_reports': RPC(instantiate=0,
                    readonly=False, result=lambda res: (
                        [{k: v for k, v in chain(
                                {key: value for key, value in report.iteritems()
                                    if key in ('report_name',)}.iteritems(),
                                {'data': base64.b64encode(report['data'])
                                    }.iteritems())}
                            for report in res[0]],
                        [attachment.id for attachment in res[1]])
                    ),
                })
        t = cls.__table__()
        cls._sql_constraints = [
            ('code_unique', Unique(t, t.code),
                'The document template code must be unique'),
            ]
        cls._error_messages.update({
                'no_version_match': 'No letter model found for date %s '
                'and language %s',
                'libre_office': 'Libre Office',
                'flat_document': 'Flat Document',
                'libre_office_odt': 'Libre Office Writer',
                'libre_office_ods': 'Libre Office Calc',
                'format_original': 'Original',
                'format_pdf': 'Pdf',
                'microsoft_office': 'Microsoft Office',
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        report_template = TableHandler(cls)
        to_update = cls.__table__()

        # Migration from 1.10 : Set recipient_needed to True for existing
        # reports
        has_recipient_needed = report_template.column_exist('recipient_needed')

        # Migration from 1.10 Rename output kind to input_kind kind
        has_column_output_kind = report_template.column_exist('output_kind')
        if has_column_output_kind:
            report_template.column_rename('output_kind', 'input_kind')

        has_column_template_extension = report_template.column_exist(
            'template_extension')
        has_column_mail_subject = report_template.column_exist('mail_subject')
        has_column_mail_body = report_template.column_exist('mail_body')
        # Migration from 1.11 Rename output_method
        has_column_output_method = report_template.column_exist('output_method')
        if has_column_output_method:
            report_template.column_rename('output_method', 'process_method')
            cursor.execute(*to_update.update(
                columns=[to_update.process_method],
                values=['libre_office'],
                where=to_update.process_method == 'open_document'))

        super(ReportTemplate, cls).__register__(module_name)
        if has_column_template_extension:
            # Migration from 1.10 Merge template extension and input_kind
            cursor.execute("UPDATE report_template "
                "SET input_kind = 'libre_office_odt' "
                "WHERE template_extension = 'odt' "
                "and input_kind='model'")
            cursor.execute("UPDATE report_template "
                "SET input_kind = 'libre_office_ods' "
                "WHERE template_extension = 'ods' "
                "and input_kind='model'")
            cursor.execute("UPDATE report_template "
                "SET input_kind = 'flat_document' "
                "WHERE process_method = 'flat_document'")
            cursor.execute("UPDATE report_template "
                "SET process_method = 'libre_office' "
                "WHERE process_method = 'open_document'")
            report_template.drop_column('template_extension')

        if not has_recipient_needed:
            cursor.execute(*to_update.update(
                    columns=[to_update.recipient_needed],
                    values=[Literal(True)]))

        if not has_column_output_kind:
            cursor.execute(*to_update.update(columns=[to_update.input_kind],
                    values=[Literal(cls.default_input_kind())],
                    where=to_update.input_kind == Null))

        if not has_column_output_method:
            # Migration from 1.10: New module report_engine_email
            cursor.execute(*to_update.update(columns=[to_update.process_method],
                    values=[Literal(cls.default_process_method())],
                    where=to_update.process_method == ''))
        if has_column_mail_subject:
            # Migration from 1.10: New module report_engine_email
            report_template.drop_column('mail_subject')
        if has_column_mail_body:
            # Migration from 1.10: New module report_engine_email
            report_template.drop_column('mail_body')

        # Migration from 1.10: Replace support from xls to xlsx
        cursor.execute(*to_update.update(
            columns=[to_update.format_for_internal_edm],
            values=['microsoft_office'],
            where=to_update.format_for_internal_edm.in_(['xls95', 'xlsx'])))

        # Migration from 1.10 move convert_to_pdf to output_format
        if report_template.column_exist('convert_to_pdf'):
            cursor.execute(*to_update.update(columns=[to_update.output_format],
                    values=['libre_office'],
                    where=to_update.convert_to_pdf == Literal(False) &
                    to_update.input_kind.in_(
                        ['libre_office_odt', 'libre_office_ods'])))
            cursor.execute(*to_update.update(columns=[to_update.output_format],
                    values=['pdf'],
                    where=to_update.convert_to_pdf == Literal(True)))
            report_template.drop_column('convert_to_pdf')
        # Ensure we have no "Null" kind in report _template table
        cursor.execute(*to_update.update(columns=[to_update.kind],
                values=[''],
                where=to_update.kind == Null))

    @classmethod
    def default_process_method(cls):
        return 'libre_office'

    @classmethod
    def default_recipient_needed(cls):
        return False

    @classmethod
    def default_kind(cls):
        return ''

    @fields.depends('input_kind')
    def get_possible_process_methods(self):
        if self.input_kind and self.input_kind.startswith('libre_office'):
            return [('libre_office',
                self.raise_user_error('libre_office', raise_exception=False))]
        elif self.input_kind == 'flat_document':
            return [('flat_document',
                self.raise_user_error('flat_document', raise_exception=False))]
        return [('', '')]

    @classmethod
    def copy(cls, reports, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('event_type_actions', None)
        return super(ReportTemplate, cls).copy(reports, default=default)

    @fields.depends('input_kind')
    def on_change_with_nb_of_possible_process_methods(self, name=None):
        return len(self.get_possible_process_methods())

    @fields.depends('process_method', 'output_format')
    def get_available_formats(self):
        available_format = [
            ('', ''),
            ]
        if self.process_method == 'libre_office':
            available_format += [
                ('original', self.__class__.raise_user_error(
                        'format_original', raise_exception=False)),
                ('microsoft_office', self.__class__.raise_user_error(
                        'microsoft_office', raise_exception=False)),
                ('pdf', self.__class__.raise_user_error(
                        'format_pdf', raise_exception=False))]
        elif self.process_method == 'flat_document':
            available_format += [
                ('original', self.__class__.raise_user_error(
                        'format_original', raise_exception=False)),
                ]
        return available_format

    def get_extension(self, var_name='output_format'):
        format_ = getattr(self, var_name)
        if not format_:
            return None
        if (format_ == 'microsoft_office'
                and self.input_kind.startswith('libre_office')):
            return {'odt': 'docx', 'ods': 'xlsx'}[self.input_kind[-3:]]
        elif format_ == 'pdf':
            return 'pdf'
        elif self.input_kind.startswith('libre_office') and (
                format_.startswith('libre_office') or format_ == 'original'):
            return self.input_kind[-3:]
        elif self.input_kind == 'flat_document':
            return os.path.splitext(self.versions[0].name)[1][1:]

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
    def default_input_kind(cls):
        return 'libre_office_odt'

    @classmethod
    def get_possible_input_kinds(cls):
        return [
            ('libre_office_odt', cls.raise_user_error('libre_office_odt',
                    raise_exception=False)),
            ('libre_office_ods', cls.raise_user_error('libre_office_ods',
                    raise_exception=False)),
            ('flat_document', cls.raise_user_error('flat_document',
                    raise_exception=False)),
            ]

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return super(ReportTemplate, cls)._export_light() | {'products',
            'document_desc', 'on_model'}

    @classmethod
    def _export_skips(cls):
        return super(ReportTemplate, cls)._export_skips() | {
            'event_type_actions'}

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

    @fields.depends('input_kind', 'possible_process_methods')
    def on_change_input_kind(self):
        possible_process_methods = self.get_possible_process_methods()
        if len(possible_process_methods) == 1:
            self.process_method = possible_process_methods[0][0]
        elif (not possible_process_methods or self.process_method not in
                [m[0] for m in self.possible_process_methods]):
            self.process_method = None
        if (not self.input_kind
                or not self.input_kind.startswith('libre_office')):
            self.output_format = None

    @fields.depends('process_method', 'format_for_internal_edm')
    def on_change_process_method(self):
        if self.process_method == 'flat_document':
            self.format_for_internal_edm = 'original'

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
        ReportGenerate = Pool().get('report.generate', type='report')
        data = context_['reporting_data']
        records = ReportGenerate._get_records(data['ids'], data['model'],
            data)
        with ServerContext().set_context(
                genshi_context=ReportGenerate.get_context(records, data)):
            if self.genshi_evaluated_export_dir:
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
            if not self.output_filename:
                filename = coog_string.slugify(filename)
                if add_time:
                    filename += '_' + datetime.now().strftime("%H%M%S%f")
            filename += ext
            out_path = os.path.join(export_dirname, filename)
            report['export_filename'] = out_path
            with open(out_path, 'a') as out:
                out.write(report['data'])

    def convert(self, data, to_ext, from_ext=None):
        pool = Pool()
        ReportModel = pool.get('report.generate', type='report')
        Report = pool.get('ir.action.report')
        input_ext = from_ext or self.get_extension('input_kind')
        if input_ext == to_ext or not to_ext:
            return input_ext, data
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data, 'utf8')
        return ReportModel.convert(
            Report(template_extension=input_ext, extension=to_ext), data)

    def _create_attachment_from_report(self, report):
        """ Report is a dictionary with:
            object_instance, report type, data, report name"""

        pool = Pool()
        Attachment = pool.get('ir.attachment')
        attachment = Attachment()
        attachment.resource = (report.get('resource') or
            report['object'].get_reference_object_for_edm(self))
        oext, attachment.data = self.convert(
            report['original_data'] or report['data'],
            self.get_extension('format_for_internal_edm'),
            report['original_ext'] or report['report_type'])
        os_extsep = os.extsep if oext else ''
        attachment.name = report['report_name_wo_ext'] + os_extsep + oext
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
            'objects': objects,
            }
        reporting_data.update(context_)
        context_['reporting_data'] = reporting_data
        if self.parameters:
            reporting_data.update({
                    x.name_in_template: reporting_data.get(x.name_in_template,
                        None) for x in self.parameters})
        functional_date = context_.get('functional_date')
        if functional_date and functional_date != utils.today():
            with Transaction().set_context(
                    client_defined_date=functional_date):
                orig_ext, orig_data, _, report_name = ReportModel.execute(
                    objects_ids, reporting_data)
        else:
            orig_ext, orig_data, _, report_name = ReportModel.execute(
                objects_ids, reporting_data)
        extension, data = self.convert(orig_data,
            self.get_extension('output_format'), orig_ext)

        return {
            'object': objects[0],
            'report_type': extension,
            'original_data': orig_data,
            'original_ext': orig_ext,
            'data': data,
            'report_name': '%s%s%s' % (report_name, os.extsep if extension else
                '', extension),
            'report_name_wo_ext': report_name,
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
        assert self.on_model
        objects = Pool().get(self.on_model.model).browse(objects)
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


class ReportLightTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'report.template'

    @classmethod
    def __setup__(cls):
        super(ReportLightTemplate, cls).__setup__()
        cls.__rpc__.update({
                'light_report': RPC(),
                })

    @classmethod
    def light_report(cls, template, data):
        template = cls(template)
        target = cls._instantiate_from_data(data)
        result = template._generate_report(
            [target], {'resource': target})['data']
        if isinstance(result, basestring):
            return base64.b64encode(result)
        return result

    @classmethod
    def _instantiate_from_data(cls, data):
        return ReportData(data)


class ReportData(object):
    '''
        This class is used when printing json documents.

        Its goal is to convert the JSON data to an object that can be used to
        access the dictionnary data as attributes, and also convert special
        objects to translated tryton records :

        {"__name__": "offered.product", "id": 1}
            => TranslateModel(Pool().get('offered.product')(1))
    '''
    __name__ = 'report.data'

    def __init__(self, data):
        self.__data = data
        self.__parsed = {}

    def __contains__(self, item):
        return self.__data.__contains__(item)

    def keys(self):
        return list(self.iterkeys())

    def iterkeys(self):
        return self.__data.iterkeys()

    def values(self):
        return list(self.itervalues())

    def itervalues(self):
        return (getattr(self, k) for k in self.__data)

    def items(self):
        return list(self.iteritems())

    def iteritems(self):
        return ((k, getattr(self, k)) for k in self.__data.iterkeys())

    def __iter__(self):
        return self.__data.__iter__()

    def __getattr__(self, name):
        if name in self.__parsed:
            return self.__parsed[name]
        if name in self.__data:
            self.__parsed[name] = self.instantiate(self.__data[name])
            return self.__parsed[name]
        if name == 'id':
            return None
        if name == 'rec_name':
            return ''
        raise AttributeError

    def instantiate(self, data):
        Report = Pool().get('report.generate', type='report')
        if isinstance(data, list):
            return [self.instantiate(x) for x in data]
        elif isinstance(data, dict) and '__name__' in data:
            assert set(data.keys()) == {'__name__', 'id'}
            return Report._get_records(
                [data['id']], data['__name__'], {})[0]
        elif isinstance(data, dict):
            return ReportData(data)
        else:
            return data

    def get_contact(self):
        return None

    def get_address(self):
        return None

    def get_sender(self):
        return None

    def get_sender_address(self):
        return None

    def get_lang(self):
        return None


class ReportTemplateVersion(model.CoogSQL, model.CoogView):
    'Report Template Version'

    __name__ = 'report.template.version'

    template = fields.Many2One('report.template', 'Template',
        required=True, ondelete='CASCADE', select=True)
    start_date = fields.Date('Start date', required=True)
    end_date = fields.Date('End date')
    language = fields.Many2One('ir.lang', 'Language', required=True,
       ondelete='RESTRICT')
    data = fields.Binary('Data', filename='name')
    name = fields.Char('Name', required=True)
    path = fields.Function(fields.Char('Path'),
        'get_path', setter='setter_data')

    @classmethod
    def __register__(cls, module_name):
        super(ReportTemplateVersion, cls).__register__(module_name)
        # Migration from 1.12: migrate data from filesystem to DB
        table = cls.__table__()
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        transaction = Transaction()
        table_handler = TableHandler(cls, module_name)
        if table_handler.column_exist('resource'):
            cursor.execute(*table.update([table.template],
                [Cast(Substring(table.resource,
                            Position(',', table.resource) +
                            Literal(1)), 'INTEGER')]))
            table_handler.drop_column('resource')
        if table_handler.column_exist('file_id'):
            prefix = config.get('attachment', 'store_prefix',
                default=transaction.database.name)
            cursor.execute(*table.select(table.id, table.file_id,
                where=(table.file_id != Null)))
            for version_id, file_id in list(cursor.fetchall()):
                filename = filestore._filename(file_id, prefix=prefix)
                try:
                    data = filestore.get(file_id, prefix=prefix)
                except Exception:
                    logger.warning('Could not find template version %s' %
                        filestore._filename(file_id, prefix=prefix))
                else:
                    logger.info('Inserting data from %s' % filename)
                    cursor.execute(*table.update(
                            [table.data], [cls.data.sql_format(data)],
                            where=(table.id == version_id)))
            table_handler.drop_column('file_id')
        table_handler.drop_column('type')
        table_handler.drop_column('link')

    @classmethod
    def __setup__(cls):
        super(ReportTemplateVersion, cls).__setup__()
        cls._export_binary_fields.add('data')

    def get_path(self, name):
        return ''

    @classmethod
    def setter_data(cls, instances, name, value):
        if value:
            with file_open(value, 'rb') as template_file:
                cls.write(instances, {'data': template_file.read()})
        else:
            cls.write(instances, {'data': None})

    @classmethod
    def _export_light(cls):
        return (super(ReportTemplateVersion, cls)._export_light() |
            set(['template', 'language']))

    @staticmethod
    def default_start_date():
        return utils.today()


class Printable(Model):
    'Base class for printable objects'

    @classmethod
    def __setup__(cls):
        super(Printable, cls).__setup__()
        cls.__rpc__.update({'get_available_doc_templates': RPC(
                instantiate=0, result=lambda x: [y.id for y in x])})

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
    def delete(cls, objects):
        ReportRequests = Pool().get('report_production.request')
        requests = None
        if objects:
            requests = ReportRequests.search([
                    ('object_', 'in', [str(x) for x in objects])])
        super(Printable, cls).delete(objects)
        if requests:
            ReportRequests.delete(requests)

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
        except Exception:
            return Transaction().language

    def get_address(self):
        contact = self.get_contact()
        if not contact:
            return ''
        return contact.main_address

    def get_available_doc_templates(self, kind=None):
        pool = Pool()
        DocumentTemplate = pool.get('report.template')
        user = pool.get('res.user')(Transaction().user)

        if kind:
            domain_kind = ('kind', '=', kind)
        else:
            domain_kind = ('kind', 'in', self.get_doc_template_kind())

        domain = self.build_template_domain(domain_kind)
        if not domain:
            domain = [
                ('on_model.model', '=', self.__name__),
                ]
        domain.append(['OR', ('groups', '=', None),
                ('groups', 'in', [x.id for x in user.groups])])
        return list(set(DocumentTemplate.search(domain)))

    def build_template_domain(self, domain_kind):
        template_holders_sub_domains = self.get_template_holders_sub_domains()
        if not template_holders_sub_domains:
            return
        return [
            ('on_model.model', '=', self.__name__),
            ['OR'] + template_holders_sub_domains,
            ['OR', [domain_kind], [('kind', '=', '')]]
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


class CoogReport(Report):

    @classmethod
    def strftime(cls, value, format, lang=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if not lang:
            code = Config.get_language()
            lang = Lang.get(code)
        return lang.strftime(value, format)

    @classmethod
    def get_context(cls, records, data):
        report_context = super(CoogReport, cls).get_context(records, data)
        report_context['strftime'] = cls.strftime
        report_context['event_code'] = data.get('event_code', None)
        return report_context


class ReportGenerate(CoogReport):
    __name__ = 'report.generate'

    @classmethod
    def _get_records(cls, ids, model, data):
        if model == 'report.data':
            return ids
        translated = super(ReportGenerate, cls)._get_records(ids, model,
            data)
        if not translated:
            return translated
        TranslateModel = cls._get_report_record_class(translated[0].__class__,
            model)
        return [TranslateModel(id) for id in ids]

    @classmethod
    def _get_report_record_class(cls, klass, model):
        Model = Pool().get(model)

        class TranslateModel(klass):
            def __init__(self, *args, **kwargs):
                klass.__init__(self, *args, **kwargs)
                self.__report_fields = {}

            def __getattr__(self, name):
                try:
                    return klass.__getattr__(self, name)
                except AttributeError:
                    if name in self.__report_fields:
                        return self.__report_fields[name]
                    report_method = '_report_field_' + name
                    if not hasattr(Model, report_method):
                        raise
                # Assume super call went at least to id2record init
                record = klass._languages[self._language][self.id]
                value = getattr(record, report_method)()
                self.__report_fields[name] = value
                return value

        return TranslateModel

    @classmethod
    def process_flat_document(cls, ids, data):
        pool = Pool()
        name_giver = data.get('resource', None) or pool.get(data['model'])(
            data['id'])
        template = pool.get('report.template')(data['doc_template'][0])
        lang = Transaction().language
        if not lang:
            raise Exception('No language defined')
        version = template.get_selected_version(utils.today(), lang)
        extension = os.path.splitext(version.name)[1][1:]
        filename, ext = cls.get_filename(template, name_giver,
            pool.get('party.party')(data['party']))
        extension = ext or extension
        return (extension, version.data, False, filename)

    @classmethod
    def process_libre_office(cls, ids, data):
        pool = Pool()
        action_reports = pool.get('ir.action.report').search([
                ('report_name', '=', cls.__name__)])
        if len(action_reports) != 1:
            raise Exception('Error', 'Report (%s) not find!' % cls.__name__)
        action_report, = action_reports
        template = Pool().get('report.template')(data['doc_template'][0])
        action_report.template_extension = template.input_kind[-3:]
        action_report.extension = template.get_extension()
        rendered = cls.render(action_report,
            ServerContext().get('genshi_context', {}))
        if ServerContext().get('disable_report_conversion', False):
            oext, content = template.get_extension('input_kind'), rendered
        else:
            oext, content = cls.convert(action_report, rendered)
        name_giver = data.get('resource', None) or pool.get(data['model'])(
            data['id'])
        filename, ext = cls.get_filename(template, name_giver,
            pool.get('party.party')(data['party']))
        oext = ext or oext
        return (oext, content, False, filename)

    @classmethod
    def execute(cls, ids, data):
        report_template = Pool().get('report.template')(
            data['doc_template'][0])
        method_name = 'process_%s' % report_template.process_method
        records = cls._get_records(ids, data['model'], data)
        report_context = cls.get_context(records, data)
        with ServerContext().set_context(genshi_context=report_context):
            if hasattr(cls, method_name):
                return getattr(cls, method_name)(ids, data)
            else:
                raise NotImplementedError('Unknown kind %s' %
                    report_template.process_method)

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
        if template.output_filename:
            fn, ext = os.path.splitext(
                template.genshi_evaluated_output_filename)
            return fn, ext[1:]
        separator = cls.get_filename_separator()
        lang = getattr(party, 'lang', utils.get_user_language())
        date_suffix = cls.get_date_suffix(lang)
        time_suffix = cls.get_time_suffix()
        return separator.join([x for x in [template.name, object_.rec_name,
                    date_suffix, time_suffix] if x]), None

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
        if data['party']:
            report_context['Party'] = pool.get('party.party')(data['party'])
        else:
            report_context['Party'] = None
        if data['address']:
            report_context['Address'] = pool.get('party.address')(
                data['address'])
        else:
            report_context['address'] = None
        try:
            report_context['Lang'] = report_context['Party'].lang
        except AttributeError:
            report_context['Lang'] = utils.get_user_language()
        if data['sender']:
            report_context['Sender'] = pool.get('party.party')(data['sender'])
        else:
            report_context['Sender'] = None
        if data['sender_address']:
            report_context['SenderAddress'] = pool.get(
                'party.address')(data['sender_address'])
        else:
            report_context['SenderAddress'] = None

        def format_date(value, lang=None, format_=None):
            if lang is None:
                lang = report_context['Lang']
            return lang.strftime(value, format_ or lang.date)

        report_context['_stored_variables'] = {}

        def setVar(var_name, value):
            report_context['_stored_variables'][var_name] = value

        def getVar(var_name, default=''):
            return report_context['_stored_variables'].get(var_name, default)

        report_context['setVar'] = setVar
        report_context['getVar'] = getVar

        report_context.update({k: v for k, v in data.iteritems() if k not in
                ['party', 'address', 'sender', 'sender_address']})

        def copy_groupby(*args, **kwargs):
            for key, values in groupby(*args, **kwargs):
                yield key, list(values)

        report_context['groupby'] = copy_groupby

        report_context['Date'] = pool.get('ir.date').today()
        report_context['FDate'] = format_date
        report_context['relativedelta'] = relativedelta
        report_context['ConvertFrequency'] = coog_date.convert_frequency
        report_context['Company'] = pool.get('party.party')(
            Transaction().context.get('company'))

        def search_and_stream(*args, **kwargs):
            model_name = kwargs.pop('model_name', data['model'])
            assert model_name != 'report.data'
            Target = pool.get(model_name)
            order_func = kwargs.pop('order_func', None)
            if order_func:
                return model.order_data_stream(
                    model.search_and_stream(Target, *args, **kwargs),
                    key_func=order_func,
                    batch_size=kwargs.pop('batch_size', None))
            else:
                return model.search_and_stream(Target, *args, **kwargs)

        report_context['Search'] = search_and_stream

        if data['model'] != 'report.data':
            SelectedModel = pool.get(data['model'])
            selected_obj = SelectedModel(data['id'])
            report_context.update(selected_obj.get_publishing_context(
                    report_context))
        else:
            report_context['target'] = data['id']
        return report_context

    @classmethod
    def render(cls, report, report_context):
        pool = Pool()
        selected_obj = report_context['objects'][0]
        selected_letter = Pool().get('report.template')(
            report_context['data']['doc_template'][0])
        report.report_content = selected_letter.get_selected_version(
            utils.today(), selected_obj.get_lang()).data
        report.style_content = selected_letter.get_style_content(
            utils.today(), selected_obj)

        try:
            return super(ReportGenerate, cls).render(
                report, report_context)
        except Exception as exc:
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
            except Exception:
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
        with open(server_filepath, 'wb') as f:
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


class ReportGenerateFromFile(CoogReport):
    __name__ = 'report.generate_from_file'

    @classmethod
    def execute(cls, ids, data):
        with open(data['output_report_filepath'], 'rb') as f:
            value = bytearray(f.read())
        return (data['output_report_filepath'].split('.')[-1], value, False,
            os.path.splitext(
                os.path.basename(data['output_report_filepath']))[0])

    @classmethod
    def convert_from_file(cls, input_paths, output_report_filepath,
            input_format, output_format):
        conv_paths = []
        report = Pool().get('ir.action.report')(
            template_extension=input_format, extension=output_format)
        for input_path in input_paths:
            with open(input_path, 'rb') as f:
                data = f.read()
            oext, conv_data = cls.convert(report, data)
            output_path = os.path.splitext(input_path)[0] + '.' + oext
            with open(output_path, 'wb') as f:
                f.write(conv_data)
            conv_paths.append(output_path)
        if len(conv_paths) > 1:
            if os.path.splitext(output_report_filepath)[1] == '.pdf':
                cmd = ['gs', '-dBATCH', '-dNOPAUSE', '-q', '-sDEVICE=pdfwrite',
                    '-sOutputFile=%s' % output_report_filepath] + conv_paths
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                stdoutdata, stderrdata = proc.communicate()
                if proc.wait() != 0:
                    raise Exception(stderrdata)
                return output_report_filepath
            # TODO: handle 'zip' format for grouping of mixed files formats
        else:
            if os.path.split(output_report_filepath)[0] != os.path.split(
                    conv_paths[0])[0]:
                shutil.move(conv_paths[0], os.path.split(
                    output_report_filepath)[0])
        return os.path.join(os.path.split(output_report_filepath)[0],
            os.path.split(conv_paths[0])[1])


class ReportCreate(wizard_context.PersistentContextWizard):
    'Report Creation'

    __name__ = 'report.create'

    start_state = 'init_templates'
    init_templates = StateTransition()
    select_template = StateView('report.create.select_template',
        'report_engine.create_report_select_template_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate', 'generate', 'tryton-go-next', default=True,
                states={'invisible': False})])
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

    @property
    def multi_objects(self):
        ids = Transaction().context.get('active_ids', None)
        return ids and len(ids) > 1

    def get_instance(self):
        transaction = Transaction()
        ActiveModel = Pool().get(transaction.context.get('active_model'))
        return ActiveModel(transaction.context.get('active_id'))

    def get_instances(self):
        transaction = Transaction()
        ActiveModel = Pool().get(transaction.context.get('active_model'))
        return ActiveModel.browse(transaction.context.get('active_ids'))

    def transition_init_templates(self):
        kind = Transaction().context.get('report_kind', None)
        if self.multi_objects:
            instances = self.get_instances()
            possible_templates = None
            for instance in instances:
                if possible_templates is None:
                    possible_templates = set(
                        instance.get_available_doc_templates(kind))
                else:
                    possible_templates &= set(
                        instance.get_available_doc_templates(kind))
            self.select_template.possible_templates = [
                x for x in possible_templates if not x.recipient_needed]
            if len(self.select_template.possible_templates) == 1:
                self.select_template.template = \
                    self.select_template.possible_templates[0]
                if not self.select_template.template.parameters:
                    self.select_template.parameters = {}
                    self.select_template.recipient = None
                    self.select_template.recipient_address = None
                    return 'generate'
            return 'select_template'
        else:
            instance = self.get_instance()
            possible_templates = instance.get_available_doc_templates(kind)
            self.select_template.possible_templates = possible_templates
            if len(self.select_template.possible_templates) == 1:
                self.select_template.template = possible_templates[0]
            possible_recipients = instance.get_recipients()
            if possible_recipients:
                self.select_template.possible_recipients = possible_recipients
                self.select_template.recipient = possible_recipients[0]
            return 'select_template'

    def default_select_template(self, fields):
        return self.select_template._default_values

    def create_report_context(self, instances):
        template = self.select_template.template
        instance = instances[0]
        if self.multi_objects or not template.recipient_needed:
            recipient = None
            recipient_address = None
        else:
            recipient = self.select_template.recipient
            recipient_address = self.select_template.recipient_address
        template = self.select_template.template
        sender = instance.get_sender()
        sender_address = instance.get_sender_address()
        return {
            'id': instance.id,
            'ids': [x.id for x in instances],
            'model': instance.__name__,
            'doc_template': [template.id],
            'party': recipient.id if recipient else None,
            'address': recipient_address.id if recipient_address else None,
            'sender': sender.id if sender else None,
            'sender_address': sender_address.id if sender_address else None,
            'origin': None,
            'objects': instances,
            }

    def transition_generate(self):
        pool = Pool()
        TemplateParameter = pool.get('report.template.parameter')
        template = self.select_template.template
        parameters = {}
        if template.parameters:
            parameters = TemplateParameter.get_data_for_report(
                self.select_template.parameters)
        self.remove_edm_temp_files()
        instances = self.get_instances()
        reports = []
        groups = [instances] if not template.split_reports else [
            [x] for x in instances]
        self.wizard_context['reports'] = []
        self.wizard_context['records'] = []
        self.wizard_context['report_context'] = []
        for group in groups:
            report_context = self.create_report_context(group)
            report_context.update(parameters)
            # for a given template, there can be several reports. For
            # instance a flow template can be printed to several output
            # for some reporting tools
            sub_reports = self.report_execute([x.id for x in group], template,
                report_context)
            for report in sub_reports:
                self.finalize_report(report, group)
            reports.extend(sub_reports)
        self.preview_document.reports = reports
        if template.modifiable_before_printing:
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
        records = ReportModel._get_records(ids, report_context['model'],
            report_context)
        template = self.select_template.template
        self.wizard_context['records'].append((tuple(ids), records))
        self.wizard_context['report_context'].append(
            (tuple(ids), report_context))
        with ServerContext().set_context(
                disable_report_conversion=template.modifiable_before_printing):
            ext, filedata, prnt, file_basename = ReportModel.execute(ids,
                report_context)
        os_extsep = os.extsep if ext else ''
        client_filepath, server_filepath = ReportModel.edm_write_tmp_report(
            filedata, '%s%s%s' % (file_basename, os_extsep, ext))
        reports = [{
            'generated_report': client_filepath,
            'server_filepath': server_filepath,
            'file_basename': file_basename,
            'extension': ext,
            'template': doc_template,
            }]
        self.wizard_context['reports'].append((tuple(ids), reports))
        return reports

    def finalize_report(self, report, instances):
        instance = instances[0]
        output = instance.get_document_filename()
        report['output_report_name'] = coog_string.slugify(output,
            lower=False)
        report['output_report_filepath'] = self._get_report_filepath(report)

    def _apply_acl_rights(self, filename):
        os.chmod(filename, stat.S_IRUSR | stat.S_IXUSR | stat.S_IWUSR |
            stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)

    def _get_report_filepath(self, report):
        restrict_rights = config.getboolean('report',
            'tmp_folder_acl_restrict', default=False)
        if (self.select_template.template.output_format == 'pdf' and
                not os.path.isfile(report['server_filepath'])):
            # Generate unique temporary output report filepath
            tmp_directory = tempfile.mkdtemp()
            if not restrict_rights:
                self._apply_acl_rights(tmp_directory)
            return os.path.join(tmp_directory, coog_string.slugify(
                    report['output_report_name'], lower=False) + '.pdf')
        else:
            return report['server_filepath']

    def default_preview_document(self, fields):
        return self.preview_document._default_values

    def _line_to_display(self):
        for line in self.preview_document.reports:
            if hasattr(line, '_displayed'):
                continue
            return line

    def do_open_document(self, action):
        to_open = self._line_to_display()
        to_open._displayed = True
        return self.action_open_report(action,
            Transaction().context.get('email_print'), to_open)

    def transition_open_document(self):
        if not self._line_to_display():
            return 'post_generation'
        return 'open_document'

    def action_open_report(self, action, email_print, report):
        ext = self.select_template.template.get_extension('output_format')
        if (ext and not report.server_filepath.endswith(ext)):
            Report = Pool().get('report.generate_from_file', type='report')
            filename = Report.convert_from_file(
                [report.server_filepath],
                report.output_report_filepath,
                self.select_template.template.get_extension('input_kind'),
                ext)
        else:
            filename = report.server_filepath
        action['email_print'] = email_print
        action['direct_print'] = Transaction().context.get('direct_print')
        action['email'] = {'to': ''}
        return action, {'output_report_filepath': filename}

    def transition_post_generation(self):
        self.wizard_context['attachments'] = []
        if not self.select_template.template.format_for_internal_edm:
            return 'end'
        pool = Pool()
        ContactHistory = pool.get('party.interaction')
        instances = self.get_instances()
        for instance in instances:
            instance.post_generation()
        reports = {cur_id: report_list
            for ids, report_list in self.wizard_context['reports']
            for cur_id in ids}
        contacts = []
        for instance in instances:
            contact = self.set_contact(instance)
            if contact:
                contacts.append(contact)
            self.complete_reports(instance, reports[instance.id])
            attachment = \
                self.select_template.template.save_reports_in_edm(
                    reports[instance.id])
            if attachment:
                self.wizard_context['attachments'].append(
                    (instance.id, attachment))
        if contacts:
            ContactHistory.save(contacts)
        return 'end'

    def set_contact(self, instance):
        ContactHistory = Pool().get('party.interaction')
        contact = ContactHistory()
        recipient = self.select_template.recipient
        if recipient is None:
            recipient = instance.get_recipients()[0]
        contact.party = recipient
        contact.media = 'mail'
        contact.address = self.select_template.recipient_address
        contact.title = self.select_template.template.name
        contact.for_object_ref = instance.get_object_for_contact()
        return contact

    def complete_reports(self, instance, reports):
        for report in reports:
            self.complete_report(instance, report)

    def complete_report(self, instance, report):
        report_name_wo_ext, ext = report['file_basename'], report['extension']
        with open(report['server_filepath'], 'rb') as f:
            original_data = bytearray(f.read())
        report.update({
                'original_ext': ext.split(os.extsep)[-1],
                'report_type': ext.split(os.extsep)[-1],
                'object': instance,
                'resource': instance.get_object_for_contact(),
                'original_data': original_data,
                'origin': instance,
                'report_name_wo_ext': report_name_wo_ext,
                })


class ReportCreateSelectTemplate(model.CoogView):
    'Report Creation Select Template'

    __name__ = 'report.create.select_template'

    template = fields.Many2One('report.template', 'Template', required=True,
        domain=[('id', 'in', Eval('possible_templates'))],
        depends=['possible_templates'])
    possible_templates = fields.Many2Many('report.template', None, None,
        'Possible Templates', states={'invisible': True})
    recipient_needed = fields.Boolean('Recipient Needed',
        states={'invisible': True})
    recipient = fields.Many2One('party.party', 'Recipient',
        states={'invisible': ~Eval('template') | ~Eval('recipient_needed'),
            'required': Bool(Eval('recipient_needed', False))},
        domain=[('id', 'in', Eval('possible_recipients'))],
        depends=['possible_recipients', 'recipient_needed'])
    possible_recipients = fields.Many2Many('party.party', None, None,
        'Possible Recipients', states={'invisible': True})
    recipient_address = fields.Many2One('party.address', 'Recipient Address',
        domain=[('party', '=', Eval('recipient'))], states={
            'invisible': ~Eval('recipient') | ~Eval('template') |
            ~Eval('recipient_needed')},
        depends=['recipient', 'recipient_needed', 'template'])
    parameters = fields.Dict('report.template.parameter', 'Parameters',
        states={'invisible': ~Eval('parameters')}, depends=['parameters'])

    @fields.depends('parameters', 'recipient', 'recipient_address', 'template')
    def on_change_template(self):
        if not self.template:
            self.recipient = None
            self.on_change_recipient()
            self.parameters = {}
            self.recipient_needed = False
        else:
            self.parameters = {
                str(x.name): None for x in self.template.parameters}
            self.recipient_needed = self.template.recipient_needed

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


class ReportCreatePreviewLine(model.CoogView):
    'Report Create Preview Line'

    __name__ = 'report.create.preview.line'

    template = fields.Many2One('report.template', 'Template')
    generated_report = fields.Char('Link')
    server_filepath = fields.Char('Server Filename',
        states={'invisible': True})
    file_basename = fields.Char('Filename')
    extension = fields.Char('Extension')
    output_report_filepath = fields.Char('Output report filepath')


class ReportTemplateGroupRelation(model.CoogSQL, model.CoogView):
    'Report Template Group Relation'

    __name__ = 'report.template-res.group'

    report_template = fields.Many2One('report.template', 'Report Template',
        required=True, ondelete='CASCADE', select=True)
    group = fields.Many2One('res.group', 'Group',
        required=True, ondelete='CASCADE', select=True)
