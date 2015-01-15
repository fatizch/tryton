# -*- coding:utf-8 -*-
import sys
import base64
import traceback
import os
import subprocess
import StringIO
import shutil
import tempfile

from trytond.config import config
from trytond.model import Model
from trytond.pool import Pool
from trytond.wizard import Wizard, StateAction, StateView, Button
from trytond.wizard import StateTransition
from trytond.report import Report
from trytond.ir import Attachment
from trytond.exceptions import UserError

from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.modules.cog_utils import fields, model, utils, coop_string, export


__all__ = [
    'DocumentProductRelation',
    'DocumentTemplate',
    'DocumentTemplateVersion',
    'Printable',
    'DocumentCreateSelect',
    'DocumentCreatePreview',
    'DocumentCreatePreviewReport',
    'DocumentCreateAttach',
    'DocumentGenerateReport',
    'DocumentFromFilename',
    'DocumentCreate',
    'DocumentCreateAttach',
    ]


class DocumentTemplate(model.CoopSQL, model.CoopView, model.TaggedMixin):
    'Document Template'

    __name__ = 'document.template'
    _func_key = 'code'

    name = fields.Char('Name', required=True, translate=True)
    on_model = fields.Many2One('ir.model', 'Model',
        domain=[('printable', '=', True)], required=True, ondelete='RESTRICT')
    code = fields.Char('Code', required=True)
    versions = fields.One2Many('document.template.version', 'resource',
        'Versions')
    kind = fields.Selection('get_possible_kinds', 'Kind')
    products = fields.Many2Many('document.template-offered.product',
        'document_template', 'product', 'Products')
    mail_subject = fields.Char('eMail Subject')
    mail_body = fields.Text('eMail Body')
    internal_edm = fields.Boolean('Use Internal EDM')
    document_desc = fields.Many2One('document.description',
        'Document Description', ondelete='SET NULL')

    @classmethod
    def __setup__(cls):
        super(DocumentTemplate, cls).__setup__()
        cls._sql_constraints = [
            ('code_unique', 'UNIQUE(code)',
                'The document template code must be unique'),
            ]
        cls._error_messages.update({
                'no_version_match': 'No letter model found for date %s '
                'and language %s',
                })

    @classmethod
    def _export_light(cls):
        return super(DocumentTemplate, cls)._export_light() | {'products',
            'document_desc', 'on_model'}

    def get_selected_version(self, date, language):
        for version in self.versions:
            if (not version.language == language
                    and not version.language.code == language):
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
        return []

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class DocumentProductRelation(model.CoopSQL):
    'Document template to Product relation'

    __name__ = 'document.template-offered.product'

    document_template = fields.Many2One('document.template', 'Document',
        ondelete='RESTRICT')
    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')


class DocumentTemplateVersion(Attachment, export.ExportImportMixin):
    'Document Template Version'

    __name__ = 'document.template.version'
    _table = None

    start_date = fields.Date('Start date', required=True)
    end_date = fields.Date('End date')
    language = fields.Many2One('ir.lang', 'Language', required=True,
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(DocumentTemplateVersion, cls).__setup__()
        cls.type.states = {'readonly': True}
        cls.resource.selection = [('document.template', 'Document Template')]

    @classmethod
    def default_type(cls):
        return 'data'

    @classmethod
    def _export_light(cls):
        return (super(DocumentTemplateVersion, cls)._export_light() |
            set(['resource', 'language']))

    @classmethod
    def _export_skips(cls):
        return (super(DocumentTemplateVersion, cls)._export_skips() |
            set(['digest', 'collision']))

    @classmethod
    def _import_json(cls, values, main_object=None):
        if 'data' in values:
            values['data'] = base64.b64decode(values['data'])
        return super(DocumentTemplateVersion, cls)._import_json(values,
            main_object)

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None):
        new_values = super(Attachment, self).export_json(skip_fields,
            already_exported, output, main_object)
        new_values['data'] = base64.b64encode(self.data) if self.data else ''
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
    @model.CoopView.button_action('offered_insurance.letter_generation_wizard')
    def generic_send_letter(cls, objs):
        pass

    def get_contact(self):
        raise NotImplementedError

    def get_lang(self):
        try:
            return self.get_contact().lang.code
        except:
            return 'en_us'

    def get_address(self, kind=None):
        contact = self.get_contact()
        if not contact:
            return ''
        if kind:
            address = [adr for adr in contact.addresses if adr.kind == kind][0]
        else:
            address = contact.addresses[0]
        return address.full_address

    def get_available_doc_templates(self, kind=None):
        DocumentTemplate = Pool().get('document.template')

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

    def get_document_filename(self):
        return self.rec_name


class DocumentCreateSelect(model.CoopView):
    'Document Create Select'

    __name__ = 'document.create.select'

    models = fields.Many2Many('document.template', None, None, 'Models',
        domain=[('id', 'in', Eval('available_models'))],
        depends=['available_models'])
    available_models = fields.Many2Many('document.template', None, None,
        'Available Models', states={'readonly': True, 'invisible': True})
    good_address = fields.Many2One('party.address', 'Mail Address',
        domain=[('party', '=', Eval('party'))], depends=['party'],
        required=True)
    party = fields.Many2One('party.party', 'Party',
        states={'invisible': True})


class DocumentGenerateReport(Report):
    __name__ = 'document.generate.report'

    @classmethod
    def execute(cls, ids, data):
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
        selected_obj = SelectedModel(data['id'])
        selected_party = pool.get('party.party')(data['party'])
        Date = pool.get('ir.date')
        filename = '%s - %s - %s' % (selected_letter.name,
            selected_obj.get_rec_name(''),
            Date.date_as_string(utils.today(), selected_party.lang))
        type, data = cls.parse(action_report, records, data, {})
        return (type, buffer(data), action_report.direct_print, filename)

    @classmethod
    def parse(cls, report, records, data, localcontext):
        pool = Pool()
        localcontext['Party'] = pool.get('party.party')(data['party'])
        localcontext['Address'] = pool.get('party.address')(data['address'])
        try:
            localcontext['Lang'] = localcontext['Party'].lang.code
        except AttributeError:
            localcontext['Lang'] = pool.get('ir.lang').search([
                    ('code', '=', 'en_US')])[0]
        if data['sender']:
            localcontext['Sender'] = pool.get('party.party')(data['sender'])
        else:
            localcontext['Sender'] = None
        if data['sender_address']:
            localcontext['SenderAddress'] = pool.get(
                'party.address')(data['sender_address'])
        else:
            localcontext['SenderAddress'] = None

        def format_date(value, lang=None):
            if lang is None:
                lang = localcontext['Party'].lang
            return pool.get('ir.lang').strftime(value, lang.code, lang.date)

        localcontext['Date'] = pool.get('ir.date').today()
        localcontext['FDate'] = format_date
        # localcontext['Logo'] = data['logo']
        SelectedModel = pool.get(data['model'])
        selected_obj = SelectedModel(data['id'])
        localcontext.update(selected_obj.get_publishing_context(localcontext))
        selected_letter = data['doc_template'][0]
        report.report_content = selected_letter.get_selected_version(
            utils.today(), selected_obj.get_lang()).data
        try:
            return super(DocumentGenerateReport, cls).parse(
                report, records, data, localcontext)
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
                    DocumentCreate = pool.get('document.create', type='wizard')
                    DocumentCreate.raise_user_error('parsing_error', (
                            frame[2][14:-2], str(exc)))
                else:
                    raise exc
            except UserError:
                raise
            except:
                pass
            raise exc

    @classmethod
    def EDM_write_tmp_report(cls, report_data, filename):
        basename, ext = os.path.splitext(filename)
        filename = coop_string.slugify(basename, lower=False) + ext
        server_shared_folder = config.get('EDM', 'server_shared_folder',
            '/tmp')
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


class DocumentFromFilename(Report):
    __name__ = 'document.generate.file_report'

    @classmethod
    def execute(cls, ids, data):
        with open(data['output_report_filepath'], 'r') as f:
            value = buffer(f.read())
        return ('.pdf', value, False,
            os.path.splitext(
                os.path.basename(data['output_report_filepath']))[0])

    @classmethod
    def generate_single_attachment(cls, input_paths, output_report_filepath):
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
        cmd = ['unoconv',
            '--connection=%s' % config.get('report', 'unoconv'),
            '-f', oext] + filepaths
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        stdoutdata, stderrdata = proc.communicate()
        if proc.wait() != 0:
            raise Exception(stderrdata)
        output_paths = [os.path.splitext(f)[0] + '.' + output_format for
            f in filepaths]
        return output_paths


class DocumentCreatePreviewReport(model.CoopView):
    'Document Create Preview Report'

    __name__ = 'document.create.preview.report'

    generated_report = fields.Char('Link')
    server_filepath = fields.Char('Server Filename',
        states={'invisible': True})
    file_basename = fields.Char('Filename')


class DocumentCreatePreview(model.CoopView):
    'Document Create Preview'

    __name__ = 'document.create.preview'

    party = fields.Many2One('party.party', 'Party',
        states={'invisible': True})
    reports = fields.One2Many('document.create.preview.report', None,
        'Reports', states={'readonly': True})
    output_report_name = fields.Char('Output Report Name')
    email = fields.Char('eMail')
    output_report_filepath = fields.Char('Output Report Filepath',
        states={'invisible': True})

    @fields.depends('output_report_name')
    def on_change_with_output_report_filepath(self, name=None):
        # Generate unique temporary output report filepath
        return os.path.join(tempfile.mkdtemp(),
            coop_string.slugify(self.output_report_name, lower=False) + '.pdf')


class DocumentCreateAttach(model.CoopView):
    'Document Create Attach'

    __name__ = 'document.create.attach'

    attachment = fields.Binary('Data File', filename='name')
    name = fields.Char('Filename')


class DocumentCreate(Wizard):
    __name__ = 'document.create'

    start_state = 'select_model'
    post_generation = StateTransition()
    select_model = StateView('document.create.select',
        'offered_insurance.document_create_select_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Preview', 'preview_document', 'tryton-go-next',
                states={'readonly': ~Eval('models')}, default=True),
            ])
    preview_document = StateView('document.create.preview',
        'offered_insurance.document_create_preview_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'select_model', 'tryton-go-previous'),
            Button('Mail', 'mail', 'tryton-go-next', default=True)
            ])
    mail = StateAction('offered_insurance.generate_file_report')
    attach = StateView('document.create.attach',
        'offered_insurance.document_create_attach_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Complete', 'post_generation', 'tryton-ok', default=True)])
    attach_to_contact = StateTransition()

    @classmethod
    def __setup__(cls):
        super(DocumentCreate, cls).__setup__()
        cls._error_messages.update({
                'parsing_error': 'Error while generating the letter:\n\n'
                '  Expression:\n%s\n\n  Error:\n%s',
                })

    def default_select_model(self, fields):
        if self.select_model._default_values:
            return self.select_model._default_values
        result = {}
        ActiveModel = Pool().get(Transaction().context.get('active_model'))
        instance = ActiveModel(Transaction().context.get('active_id'))
        if not instance:
            return {}
        result['available_models'] = [elem.id for elem in
            instance.get_available_doc_templates()]
        result['party'] = instance.get_contact().id
        if instance.get_contact().addresses:
            result['good_address'] = instance.get_contact().addresses[0].id
        return result

    def default_preview_document(self, fields):
        self.remove_EDM_temp_files()
        pool = Pool()
        ReportModel = pool.get('document.generate.report', type='report')
        ContactMechanism = pool.get('party.contact_mechanism')
        ActiveModel = pool.get(Transaction().context.get('active_model'))
        printable_inst = ActiveModel(Transaction().context.get('active_id'))
        sender = printable_inst.get_sender()
        sender_address = printable_inst.get_sender_address()
        result = {'reports': []}
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
                ReportModel.EDM_write_tmp_report(filedata,
                    '%s.%s' % (file_basename, ext))
            result['reports'].append({'generated_report': client_filepath,
                    'server_filepath': server_filepath,
                    'file_basename': file_basename
            })
        email = ContactMechanism.search([
                ('party', '=', self.select_model.party.id),
                ('type', '=', 'email'),
                ])
        if email:
            result['email'] = email[0].value
        output = printable_inst.get_document_filename()
        if len(result['reports']) == 1:
            model_name = os.path.splitext(
                result['reports'][0]['file_basename'])[0]
            output = '%s-%s' % (output, model_name)
        result['output_report_name'] = coop_string.slugify(output, lower=False)
        result['party'] = self.select_model.party.id
        return result

    def do_mail(self, action):
        pool = Pool()
        Report = pool.get('document.generate.file_report', type='report')
        Report.generate_single_attachment(
            [d.server_filepath for d in self.preview_document.reports],
            self.preview_document.output_report_filepath)
        action['email_print'] = True
        action['email'] = {'to': self.preview_document.email}
        return action, {
            'output_report_filepath':
                self.preview_document.output_report_filepath,
        }

    def transition_mail(self):
        if all([not model.internal_edm for model in self.select_model.models]):
            return 'end'
        return 'attach'

    def default_attach(self, fields):
        with open(self.preview_document.output_report_filepath, 'r') as f:
            attachment = buffer(f.read())
        result = {'attachment': attachment,
            'name': os.path.basename(
                self.preview_document.output_report_filepath),
        }
        return result

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

    def remove_EDM_temp_files(self):
        try:
            for f in self.preview_document.reports:
                shutil.rmtree(os.path.dirname(f.server_filepath))
        except (AttributeError, OSError):
            # no reports or report already removed
            pass

    def end(self):
        self.remove_EDM_temp_files()
