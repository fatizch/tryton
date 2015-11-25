# -*- coding:utf-8 -*-
import sys
import traceback
import logging
import os
import subprocess
import StringIO
import shutil
import tempfile

from time import sleep
from datetime import datetime

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
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model, utils, coop_string, export

logger = logging.getLogger(__name__)

__all__ = [
    'ReportTemplate',
    'ReportTemplateVersion',
    'Printable',
    'ReportCreateSelectTemplate',
    'ReportCreatePreview',
    'ReportCreatePreviewLine',
    'ReportGenerate',
    'ReportGenerateFromFile',
    'ReportCreate',
    'ReportCreateAttach',
    ]

FILE_EXTENSIONS = [
    ('odt', 'Open Document Text (.odt)'),
    ('odp', 'Open Document Presentation (.odp)'),
    ('ods', 'Open Document Spreadsheet (.ods)'),
    ('odg', 'Open Document Graphics (.odg)'),
    ]


class ReportTemplate(model.CoopSQL, model.CoopView, model.TaggedMixin):
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
    mail_subject = fields.Char('eMail Subject')
    mail_body = fields.Text('eMail Body')
    format_for_internal_edm = fields.Selection([
            ('', ''),
            ('original', 'Original'),
            ('pdf', 'Pdf'),
            ], 'Format for internal EDM', help="If no format is specified, "
            "the document will not be stored in the internal EDM")
    document_desc = fields.Many2One('document.description',
        'Document Description', ondelete='SET NULL')
    modifiable_before_printing = fields.Boolean('Modifiable',
        help='Set to true if you want to modify the generated document before '
        'sending or printing')
    template_extension = fields.Selection(FILE_EXTENSIONS,
        'Template Extension')
    export_dir = fields.Char('Export Directory', help='Store a copy of each '
        'generated document in specified server directory')
    convert_to_pdf = fields.Boolean('Convert to pdf')
    split_reports = fields.Boolean('Split Reports', help="If checked,"
        " one document will be produced for each object. If not checked"
        " a single document will be produced for several objects.")
    event_type_actions = fields.Many2Many('event.type.action-report.template',
            'report_template', 'event_type_action', 'Event Type Actions')

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
                })

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.3: rename 'document_template' => 'report_template'
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        if TableHandler.table_exist(cursor, 'document_template'):
            TableHandler.table_rename(cursor, 'document_template',
                'report_template')
        report_template = TableHandler(cursor, cls)
        has_column_template_extension = report_template.column_exist(
            'template_extension')
        has_column_internal_edm = report_template.column_exist('internal_edm')
        super(ReportTemplate, cls).__register__(module_name)
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

    @classmethod
    def _export_light(cls):
        return super(ReportTemplate, cls)._export_light() | {'products',
            'document_desc', 'on_model', 'event_types'}

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
        for version in self.versions:
            if (not version.language == language and
                    not version.language.code == language):
                continue
            if version.start_date > date:
                continue
            if not version.end_date:
                return version
            if version.end_date >= date:
                return version
        self.raise_user_error('no_version_match', (date, language))

    @fields.depends('on_model')
    def get_possible_kinds(self):
        return [('', '')]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    def print_reports(self, reports, context_):
        """ Reports is a list of dicts with keys:
            object, origin, report type, data, report name"""
        if self.export_dir:
            self.export_reports(reports)

    def export_reports(self, reports):
        export_dir_basename = os.path.basename(self.export_dir)
        if export_dir_basename != self.export_dir:
            logger.warning("Keep only '%s' part of '%s' export_dir setting" %
                (export_dir_basename, self.export_dir))
        export_root_dir = config.get('report', 'export_root_dir')
        if not export_root_dir:
            raise Exception('Error', "No 'export_root_dir' configuration "
                'setting specified.')
        export_dirname = os.path.join(
            export_root_dir, export_dir_basename)
        if not os.path.exists(export_dirname):
            raise Exception('Error', 'Export directory does not exist: %s' %
                export_dir_basename)
        for report in reports:
            filename, ext = os.path.splitext(report['report_name'])
            out_path = os.path.join(
                export_dirname,
                '%s_%s%s' % (coop_string.slugify(filename),
                    datetime.now().strftime("%H%M%S%f"), ext))
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
        attachment.origin = report['origin']
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
                }
        reporting_data.update(context_)
        functional_date = context_.get('functional_date')
        if functional_date:
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
        cursor = Transaction().cursor
        if TableHandler.table_exist(cursor, 'document_template_version'):
            TableHandler.table_rename(cursor,
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

    @classmethod
    def _import_json(cls, values, main_object=None):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        Attachment.decode_binary_data(values)
        return super(ReportTemplateVersion, cls)._import_json(values,
            main_object)

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None, configuration=None):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        new_values = super(ReportTemplateVersion, self).export_json(
            skip_fields, already_exported, output, main_object, configuration)
        Attachment.encode_binary_data(new_values, configuration, self)
        return new_values


class Printable(Model):

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
    @model.CoopView.button_action('report_engine.letter_generation_wizard')
    def generic_send_letter(cls, objs):
        pass

    def get_contact(self):
        raise NotImplementedError

    def get_lang(self):
        try:
            return self.get_contact().lang.code
        except:
            return 'en_us'

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
        if hasattr(self, 'product'):
            domain = [
                ('on_model.model', '=', self.__name__),
                ('products', '=', self.product.id),
                ['OR',
                    domain_kind,
                    ('kind', '=', '')],
                ]
        else:
            domain = [
                ('on_model.model', '=', self.__name__),
                ]
        return DocumentTemplate.search(domain)

    def get_doc_template_kind(self):
        return None

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
            'Today': utils.today(),
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


class ReportCreateSelectTemplate(model.CoopView):
    'Report Create Select Template'

    __name__ = 'report.create.select_template'

    models = fields.Many2Many('report.template', None, None, 'Models',
        domain=[('id', 'in', Eval('available_models'))],
        depends=['available_models'])
    available_models = fields.Many2Many('report.template', None, None,
        'Available Models', states={'readonly': True, 'invisible': True})
    good_address = fields.Many2One('party.address', 'Mail Address',
        domain=[('party', '=', Eval('party'))], depends=['party'],
        required=True)
    party = fields.Many2One('party.party', 'Party',
        states={'invisible': True})


class ReportGenerate(Report):
    __name__ = 'report.generate'

    @classmethod
    def execute(cls, ids, data, immediate_conversion=False):
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
        selected_letter = data['doc_template'][0]
        SelectedModel = pool.get(data['model'])
        name_giver = data.get('resource', None) or SelectedModel(data['id'])
        selected_party = pool.get('party.party')(data['party'])
        filename = cls.get_filename(selected_letter, name_giver,
            selected_party)
        report_context = cls.get_context(records, data)
        action_report.template_extension = selected_letter.template_extension
        if immediate_conversion and selected_letter.format_for_internal_edm \
                not in ('', 'original'):
            action_report.extension = selected_letter.format_for_internal_edm
        oext, content = cls.convert(action_report,
            cls.render(action_report, report_context))
        return (oext, bytearray(content), action_report.direct_print, filename)

    @classmethod
    def get_filename_separator(cls):
        return ' - '

    @classmethod
    def get_date_suffix(cls, language):
        pool = Pool()
        Date = pool.get('ir.date')
        return coop_string.slugify(
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
        report_context['Party'] = pool.get('party.party')(data['party'])
        report_context['Address'] = pool.get('party.address')(data['address'])
        try:
            report_context['Lang'] = report_context['Party'].lang.code
        except AttributeError:
            report_context['Lang'] = pool.get('ir.lang').search([
                    ('code', '=', 'en_US')])[0]
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
        selected_letter = report_context['data']['doc_template'][0]
        report.report_content = selected_letter.get_selected_version(
            utils.today(), selected_obj.get_lang()).data
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
    def edm_write_tmp_report(cls, report_data, filename):
        basename, ext = os.path.splitext(filename)
        filename = coop_string.slugify(basename, lower=False) + ext
        server_shared_folder = config.get('EDM', 'server_shared_folder',
            default='/tmp')
        client_shared_folder = config.get('EDM', 'client_shared_folder')
        try:
            tmp_dir = os.path.basename(
                tempfile.mkdtemp(dir=server_shared_folder))
        except OSError as e:
            raise Exception('Could not create tmp_directory in %s (%s)' %
                (server_shared_folder, e))
        tmp_suffix_path = os.path.join(tmp_dir, filename)
        server_filepath = os.path.join(server_shared_folder, tmp_suffix_path)
        client_filepath = os.path.join(client_shared_folder, tmp_suffix_path) \
            if client_shared_folder else ''
        with open(server_filepath, 'w') as f:
            f.write(report_data)
            return(client_filepath, server_filepath)


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
        cmd = ['unoconv', '--connection=%s' % config.get('report', 'unoconv'),
            '-f', oext] + filepaths
        for num_try in range(3):
            # unoconv crashes randomly, re-running it usually suffices to
            # resolve the problem
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            stdoutdata, stderrdata = proc.communicate()
            if proc.wait() == 0:
                break
            sleep(.5)
        else:
            raise Exception(stderrdata)
        output_paths = [os.path.splitext(f)[0] + '.' + output_format for
            f in filepaths]
        return output_paths


class ReportCreatePreviewLine(model.CoopView):
    'Report Create Preview Line'

    __name__ = 'report.create.preview.line'

    template = fields.Many2One('report.template', 'Template')
    generated_report = fields.Char('Link')
    server_filepath = fields.Char('Server Filename',
        states={'invisible': True})
    file_basename = fields.Char('Filename')


class ReportCreatePreview(model.CoopView):
    'Report Create Preview'

    __name__ = 'report.create.preview'

    party = fields.Many2One('party.party', 'Party',
        states={'invisible': True})
    reports = fields.One2Many('report.create.preview.line', None,
        'Reports', states={'readonly': True})
    output_report_name = fields.Char('Output Report Name')
    email = fields.Char('eMail')
    output_report_filepath = fields.Char('Output Report Filepath',
        states={'invisible': True})

    @fields.depends('output_report_name', 'reports')
    def on_change_with_output_report_filepath(self, name=None):
        if all([x.template.convert_to_pdf for x in self.reports]):
            # Generate unique temporary output report filepath
            return os.path.join(tempfile.mkdtemp(), coop_string.slugify(
                        self.output_report_name, lower=False) + '.pdf')
        else:
            return self.reports[0].server_filepath


class ReportCreateAttach(model.CoopView):
    'Report Create Attach'

    __name__ = 'report.create.attach'

    attachment = fields.Binary('Data File', filename='name')
    name = fields.Char('Filename')


class ReportCreate(Wizard):
    __name__ = 'report.create'

    start_state = 'select_model_needed'
    select_model_needed = StateTransition()
    select_model = StateView('report.create.select_template',
        'report_engine.document_create_select_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate', 'generate_reports', 'tryton-go-next',
                states={'readonly': ~Eval('models')}, default=True),
            ])
    generate_reports = StateTransition()
    preview_document = StateView('report.create.preview',
        'report_engine.document_create_preview_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'select_model', 'tryton-go-previous'),
            Button('Mail', 'mail', 'tryton-print-email', default=True),
            Button('Open', 'open_document', 'tryton-print-open')
            ])
    open_document = StateAction('report_engine.generate_file_report')
    mail = StateAction('report_engine.generate_file_report')
    attach = StateView('report.create.attach',
        'report_engine.document_create_attach_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Save', 'post_generation', 'tryton-save',
                default=True)])
    post_generation = StateTransition()
    attach_to_contact = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ReportCreate, cls).__setup__()
        cls._error_messages.update({
                'parsing_error': 'Error while generating the letter:\n\n'
                '  Expression:\n%s\n\n  Error:\n%s',
                })

    def transition_select_model_needed(self):
        ActiveModel = Pool().get(Transaction().context.get('active_model'))
        instance = ActiveModel(Transaction().context.get('active_id'))
        if not instance:
            return 'select_model'
        self.select_model.available_models = [elem.id for elem in
            instance.get_available_doc_templates()]
        if len(self.select_model.available_models) == 1:
            self.select_model.models = self.select_model.available_models
        self.select_model.party = instance.get_contact().id
        if instance.get_contact().addresses:
            addresses = instance.get_contact().addresses
            self.select_model.good_address = addresses[0].id
            if len(addresses) == 1 and getattr(self.select_model, 'models',
                    []):
                return 'generate_reports'
        return 'select_model'

    def default_select_model(self, fields):
        return self.select_model._default_values

    def transition_generate_reports(self):
        self.remove_edm_temp_files()
        pool = Pool()
        ReportModel = pool.get('report.generate', type='report')
        ContactMechanism = pool.get('party.contact_mechanism')
        ActiveModel = pool.get(Transaction().context.get('active_model'))
        printable_inst = ActiveModel(Transaction().context.get('active_id'))
        sender = printable_inst.get_sender()
        sender_address = printable_inst.get_sender_address()
        reports = []
        for doc_template in self.select_model.models:
            ext, filedata, _, file_basename = ReportModel.execute(
                [Transaction().context.get('active_id')], {
                    'id': Transaction().context.get('active_id'),
                    'ids': Transaction().context.get('active_ids'),
                    'model': Transaction().context.get('active_model'),
                    'doc_template': [doc_template],
                    'party': self.select_model.party.id,
                    'address': self.select_model.good_address.id,
                    'sender': sender.id if sender else None,
                    'sender_address': sender_address.id if sender_address
                    else None,
                    })
            client_filepath, server_filepath = \
                ReportModel.edm_write_tmp_report(filedata,
                    '%s.%s' % (file_basename, ext))
            reports.append({
                    'generated_report': client_filepath,
                    'server_filepath': server_filepath,
                    'file_basename': file_basename,
                    'template': doc_template,
                    })
        self.preview_document.reports = reports
        email = ContactMechanism.search([
                ('party', '=', self.select_model.party.id),
                ('type', '=', 'email'),
                ])
        if email:
            self.preview_document.email = email[0].value
        output = printable_inst.get_document_filename()
        self.preview_document.output_report_name = coop_string.slugify(output,
            lower=False)
        self.preview_document.output_report_filepath = \
            self.preview_document.on_change_with_output_report_filepath()
        self.preview_document.party = self.select_model.party.id
        if all([x.template.modifiable_before_printing
                for x in self.preview_document.reports]):
            return 'preview_document'
        return 'open_document'

    def default_preview_document(self, fields):
        return self.preview_document._default_values

    def open_or_mail_report(self, action, email_print):
        pool = Pool()
        Report = pool.get('report.generate_from_file', type='report')
        if all([x.template.convert_to_pdf
                for x in self.preview_document.reports]):
            Report.convert_single_attachment(
                [d.server_filepath for d in self.preview_document.reports],
                self.preview_document.output_report_filepath)
            filename = self.preview_document.output_report_filepath
        else:
            filename = [d.server_filepath
            for d in self.preview_document.reports][0]
        action['email_print'] = email_print
        action['direct_print'] = Transaction().context.get('direct_print')
        action['email'] = {'to': getattr(self.preview_document, 'email', '')}
        return action, {'output_report_filepath': filename}

    def do_open_document(self, action):
        return self.open_or_mail_report(action,
            Transaction().context.get('email_print'))

    def transition_open_document(self):
        if all([not model.format_for_internal_edm
                for model in self.select_model.models]):
            return 'end'
        return 'attach'

    def do_mail(self, action):
        return self.open_or_mail_report(action, True)

    def transition_mail(self):
        if all([not model.format_for_internal_edm
                for model in self.select_model.models]):
            return 'end'
        return 'attach'

    def default_attach(self, fields):
        if any([x.template.format_for_internal_edm == 'original'
                for x in self.preview_document.reports]):
            file_name = self.preview_document.reports[0].server_filepath
        else:
            file_name = self.preview_document.output_report_filepath

        with open(file_name, 'r') as f:
            attachment = bytearray(f.read())
        return {
            'attachment': attachment,
            'name': os.path.basename(file_name),
            }

    def transition_post_generation(self):
        GoodModel = Pool().get(Transaction().context.get('active_model'))
        good_obj = GoodModel(Transaction().context.get('active_id'))
        good_obj.post_generation()
        ContactHistory = Pool().get('party.interaction')
        contact = ContactHistory()
        contact.party = good_obj.get_contact()
        contact.media = 'mail'
        contact.address = self.select_model.good_address
        contact.title = self.select_model.models[0].name
        contact.for_object_ref = good_obj.get_object_for_contact()
        if (hasattr(self, 'attach') and self.attach):
            Attachment = Pool().get('ir.attachment')
            attachment = Attachment()
            attachment.resource = contact.for_object_ref
            attachment.data = self.attach.attachment
            attachment.name = self.attach.name
            attachment.document_desc = \
                self.select_model.models[0].document_desc
            attachment.save()
            contact.attachment = attachment
        contact.save()
        return 'end'

    def remove_edm_temp_files(self):
        try:
            for f in self.preview_document.reports:
                shutil.rmtree(os.path.dirname(f.server_filepath))
        except (AttributeError, OSError):
            # no reports or report already removed
            pass
