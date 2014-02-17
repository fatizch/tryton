#-*- coding:utf-8 -*-
import os
import subprocess
import copy
import StringIO
import functools
import shutil

from trytond.config import CONFIG
from trytond.model import Model
from trytond.pool import Pool
from trytond.wizard import Wizard, StateAction, StateView, Button
from trytond.wizard import StateTransition
from trytond.report import Report
from trytond.ir import Attachment

from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.modules.cog_utils import fields, model, utils, coop_string
from trytond.modules.cog_utils import coop_date
from trytond.modules.offered_insurance.business_rule.business_rule import \
    BusinessRuleRoot, STATE_ADVANCED
from trytond.modules.cog_utils import BatchRoot

MAX_TMP_TRIES = 10

__all__ = [
    'DocumentDescription',
    'DocumentProductRelation',
    'DocumentRule',
    'RuleDocumentDescriptionRelation',
    'DocumentRequestLine',
    'DocumentRequest',
    'DocumentTemplate',
    'DocumentTemplateVersion',
    'Printable',
    'DocumentCreateSelectTemplate',
    'DocumentCreateSelect',
    'DocumentCreatePreview',
    'DocumentCreateAttach',
    'DocumentGenerateReport',
    'DocumentFromFilename',
    'DocumentCreate',
    'DocumentReceiveRequest',
    'DocumentReceiveAttach',
    'DocumentReceiveSetRequests',
    'DocumentReceive',
    'DocumentCreateAttach',
    'DocumentRequestBatch',
    ]


class DocumentTemplate(model.CoopSQL, model.CoopView):
    'Document Template'

    __name__ = 'document.template'

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

    def get_good_version(self, date, language):
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

    @fields.depends('on_model')
    def get_possible_kinds(self):
        if self.on_model and self.on_model.model == 'document.request':
            return [('doc_request', 'Document Request')]
        return []


class DocumentProductRelation(model.CoopSQL):
    'Document template to Product relation'

    __name__ = 'document.template-offered.product'

    document_template = fields.Many2One('document.template', 'Document',
        ondelete='RESTRICT')
    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')


class DocumentTemplateVersion(Attachment):
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
        cls.type = copy.copy(cls.type)
        cls.type.states = {'readonly': True}
        cls.resource = copy.copy(cls.resource)
        cls.resource.selection = [('document.template', 'Document Template')]

    @classmethod
    def default_type(cls):
        return 'data'


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
        domain = [
            ('on_model.model', '=', self.__name__),
            ('products', '=', self.get_product().id),
            ['OR',
                ('kind', '=', kind or self.get_doc_template_kind()),
                ('kind', '=', '')],
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


class DocumentDescription(model.CoopSQL, model.CoopView):
    'Document Description'

    __name__ = 'document.description'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


class DocumentRule(BusinessRuleRoot, model.CoopSQL):
    'Document Managing Rule'

    __name__ = 'document.rule'

    kind = fields.Selection([
            ('', ''),
            ('main', 'Main'),
            ('sub', 'Sub Elem'),
            ('loss', 'Loss'),
            ], 'Kind')
    documents = fields.Many2Many('document.rule-document.description', 'rule',
        'document', 'Documents', states={'invisible': STATE_ADVANCED})

    def give_me_documents(self, args):
        if self.config_kind == 'simple':
            return self.documents, []
        if not self.rule:
            return [], []
        try:
            rule_result = self.get_rule_result(args)
        except Exception:
            return [], ['Invalid rule']
        try:
            result = utils.get_those_objects(
                'document.request.line', [
                    ('code', 'in', rule_result.result)])
            return result, []
        except:
            return [], ['Invalid documents']

    @classmethod
    def default_kind(cls):
        return Transaction().context.get('doc_rule_kind', None)


class RuleDocumentDescriptionRelation(model.CoopSQL):
    'Rule to Document Description Relation'

    __name__ = 'document.rule-document.description'

    rule = fields.Many2One('document.rule', 'Rule', ondelete='CASCADE')
    document = fields.Many2One('document.description', 'Document',
        ondelete='RESTRICT')


class DocumentRequestLine(model.CoopSQL, model.CoopView):
    'Document Request Line'

    __name__ = 'document.request.line'

    document_desc = fields.Many2One('document.description',
        'Document Definition', required=True, ondelete='RESTRICT')
    for_object = fields.Reference('Needed For', [('', '')],
        states={'readonly': ~~Eval('for_object')})
    send_date = fields.Date('Send Date')
    reception_date = fields.Date('Reception Date')
    request_date = fields.Date('Request Date', states={'readonly': True})
    received = fields.Function(
        fields.Boolean('Received', depends=['attachment', 'reception_date']),
        'on_change_with_received')
    request = fields.Many2One('document.request', 'Document Request',
        ondelete='CASCADE')
    attachment = fields.Many2One('ir.attachment', 'Attachment', domain=[
            ('resource', '=', Eval('_parent_request', {}).get(
                'needed_by_str'))], ondelete='SET NULL')

    @fields.depends('attachment', 'reception_date', 'received')
    def on_change_attachment(self):
        if not (hasattr(self, 'attachment') and self.attachment):
            return {}
        return {
            'received': True,
            'reception_date': (
                hasattr(self, 'reception_date') and
                self.reception_date) or utils.today()}

    @fields.depends('reception_date')
    def on_change_with_received(self, name=None):
        if not (hasattr(self, 'reception_date') and self.reception_date):
            return False
        else:
            return True

    @fields.depends('received', 'reception_date')
    def on_change_received(self):
        if (hasattr(self, 'received') and self.received):
            if (hasattr(self, 'reception_date') and self.reception_date):
                return {}
            else:
                return {'reception_date': utils.today()}
        else:
            return {'reception_date': None}

    @fields.depends('attachment', 'reception_date')
    def on_change_with_reception_date(self, name=None):
        if (hasattr(self, 'attachment') and self.attachment):
            if (hasattr(self, 'reception_date') and self.reception_date):
                return self.reception_date
            else:
                return utils.today()

    def get_rec_name(self, name=None):
        if not (hasattr(self, 'document_desc') and self.document_desc):
            return ''

        if not (hasattr(self, 'for_object') and self.for_object):
            return self.document_desc.name

        return self.document_desc.name + ' - ' + \
            self.for_object.get_rec_name(name)

    @classmethod
    def default_request_date(cls):
        return utils.today()

    @classmethod
    def setter_void(cls, docs, values, name):
        pass

    @classmethod
    def default_for_object(cls):
        if not 'request_owner' in Transaction().context:
            return ''

        needed_by = Transaction().context.get('request_owner')

        the_model, the_id = needed_by.split(',')

        if not the_model in [
                k for k, v in cls._fields['for_object'].selection]:
            return ''

        return needed_by


class DocumentRequest(Printable, model.CoopSQL, model.CoopView):
    'Document Request'

    __name__ = 'document.request'

    needed_by = fields.Reference('Requested for', [('', '')])
    documents = fields.One2Many('document.request.line', 'request',
        'Documents', depends=['needed_by_str'],
        context={'request_owner': Eval('needed_by_str')})
    is_complete = fields.Function(
        fields.Boolean('Is Complete', depends=['documents'],
            states={'readonly': ~~Eval('is_complete')}),
        'on_change_with_is_complete', 'setter_void')
    needed_by_str = fields.Function(
        fields.Char('Master as String', depends=['needed_by']),
        'on_change_with_needed_by_str')
    request_description = fields.Function(
        fields.Char('Request Description', depends=['needed_by']),
        'on_change_with_request_description')

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls._buttons.update({'generic_send_letter': {}})

    def get_request_date(self):
        return utils.today()

    @fields.depends('needed_by')
    def on_change_with_request_description(self, name=None):
        return 'Document Request for %s' % self.needed_by.get_rec_name(name)

    def get_contact(self, name=None):
        if not (hasattr(self, 'needed_by') and self.needed_by):
            return None
        try:
            return self.needed_by.get_main_contact()
        except AttributeError:
            return None

    @fields.depends('needed_by')
    def on_change_with_needed_by_str(self, name=None):
        if not (hasattr(self, 'needed_by') and self.needed_by):
            return ''

        return utils.convert_to_reference(self.needed_by)

    @fields.depends('documents')
    def on_change_with_is_complete(self, name=None):
        if not (hasattr(self, 'documents') and self.documents):
            return True
        for doc in self.documents:
            if not doc.received:
                return False
        return True

    @fields.depends('documents', 'is_complete')
    def on_change_documents(self):
        return {'is_complete': self.on_change_with_is_complete()}

    @fields.depends('documents', 'is_complete')
    def on_change_is_complete(self):
        if not (hasattr(self, 'is_complete') or not self.is_complete):
            return {}
        if not (hasattr(self, 'documents') and self.documents):
            return {}
        return {
            'documents': {
                'update': [{
                        'id': d.id,
                        'received': True,
                        'reception_date': d.reception_date or utils.today()}
                    for d in self.documents]}}

    @classmethod
    def setter_void(cls, docs, values, name):
        pass

    def get_current_docs(self):
        if not (hasattr(self, 'documents') and self.documents):
            return {}
        res = {}
        for elem in self.documents:
            res[(
                elem.document_desc.id,
                utils.convert_to_reference(elem.for_object))] = elem
        return res

    def add_documents(self, date, docs):
        # "docs" should be a list of tuple (doc_desc, for_object)
        existing_docs = self.get_current_docs()
        Document = Pool().get('document.request.line')
        for desc, obj in docs:
            if ((desc.id, utils.convert_to_reference(obj))) in existing_docs:
                continue
            good_doc = Document()
            good_doc.document_desc = desc
            good_doc.for_object = utils.convert_to_reference(obj)
            good_doc.request = self
            good_doc.save()
            existing_docs[
                (desc.id, utils.convert_to_reference(obj))] = good_doc

    def clean_extras(self, docs):
        existing_docs = self.get_current_docs()
        id_docs = [(d.id, utils.convert_to_reference(o)) for d, o in docs]
        to_del = []
        for k, v in existing_docs.iteritems():
            if not k in id_docs:
                to_del.append(v)
        Document = Pool().get('document.request.line')
        Document.delete(to_del)

    def get_waiting_documents(self):
        return len([doc for doc in self.documents if not doc.received])

    def post_generation(self):
        for document in self.documents:
            if not document.received:
                document.send_date = utils.today()
                document.save()

    def notify_completed(self):
        pass

    def get_doc_template_kind(self):
        return 'doc_request'

    def get_object_for_contact(self):
        return self.needed_by

    def get_rec_name(self, name):
        return self.needed_by.get_rec_name(name)

    def get_product(self):
        return self.needed_by.get_product()


class DocumentCreateSelectTemplate(model.CoopView):
    'Document Create Select Template'

    __name__ = 'document.create.select.template'

    doc_template = fields.Many2One('document.template', 'Document Template')
    selected = fields.Boolean('Selected')


class DocumentCreateSelect(model.CoopView):
    'Document Create Select'

    __name__ = 'document.create.select'

    models = fields.One2Many('document.create.select.template', '', 'Models')
    good_address = fields.Many2One('party.address', 'Mail Address',
        domain=[('party', '=', Eval('party'))], depends=['party'],
        required=True)
    party = fields.Many2One('party.party', 'Party',
        states={'invisible': True})

    def get_active_model(self, id_only=True):
        for elem in self.models:
            if elem.selected:
                if id_only:
                    return elem.doc_template.id
                else:
                    return elem.doc_template


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
        DocumentTemplate = Pool().get('document.template')
        good_letter = DocumentTemplate(data['doc_template'])
        GoodModel = Pool().get(data['model'])
        good_obj = GoodModel(data['id'])
        good_party = Pool().get('party.party')(data['party'])
        filename = good_letter.name + ' - ' + good_obj.get_rec_name('') + \
            ' - ' + coop_string.date_as_string(utils.today(), good_party.lang)
        try:
            type, data = cls.parse(action_report, records, data, {})
        except:
            import traceback
            traceback.print_exc()
            raise
        return (type, buffer(data), action_report.direct_print, filename)

    @classmethod
    def parse(cls, report, records, data, localcontext):
        localcontext['Party'] = Pool().get('party.party')(data['party'])
        localcontext['Address'] = Pool().get('party.address')(data['address'])
        try:
            localcontext['Lang'] = localcontext['Party'].lang.code
        except AttributeError:
            localcontext['Lang'] = Pool().get('ir.lang').search([
                    ('code', '=', 'en_US')])[0]
        if data['sender']:
            localcontext['Sender'] = Pool().get('party.party')(data['sender'])
        else:
            localcontext['Sender'] = None
        if data['sender_address']:
            localcontext['SenderAddress'] = Pool().get(
                'party.address')(data['sender_address'])
        else:
            localcontext['SenderAddress'] = None

        def format_date(value, lang=None):
            if lang is None:
                lang = localcontext['Party'].lang
            return Pool().get('ir.lang').strftime(value, lang.code, lang.date)

        localcontext['Date'] = Pool().get('ir.date').today()
        localcontext['FDate'] = format_date
        # localcontext['Logo'] = data['logo']
        GoodModel = Pool().get(data['model'])
        good_obj = GoodModel(data['id'])
        localcontext.update(good_obj.get_publishing_context(localcontext))
        DocumentTemplate = Pool().get('document.template')
        good_letter = DocumentTemplate(data['doc_template'])
        report.report_content = good_letter.get_good_version(
            utils.today(), good_obj.get_lang()).data
        return super(DocumentGenerateReport, cls).parse(
            report, records, data, localcontext)


class DocumentFromFilename(Report):
    __name__ = 'document.generate.file_report'

    @classmethod
    def execute(cls, ids, data):
        if not 'filepath' in data:
            raise Exception('Error', 'Report %s needs to be provided with a '
                'filepath' % cls.__name__)
        if not os.path.isfile(data['filepath']):
            raise Exception('%s is not a valid filename' % data['filepath'])
        value = buffer(cls.unoconv(data['filepath'], 'odt', 'pdf'))
        return ('.pdf', value, False, data['filename'])

    @classmethod
    def unoconv(cls, filepath, input_format, output_format):
        from trytond.report import FORMAT2EXT
        oext = FORMAT2EXT.get(output_format, output_format)
        cmd = ['unoconv', '--connection=%s' % CONFIG['unoconv'],
            '-f', oext, '--stdout', filepath]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        stdoutdata, stderrdata = proc.communicate()
        if proc.wait() != 0:
            raise Exception(stderrdata)
        return stdoutdata


class DocumentCreatePreview(model.CoopView):
    'Document Create Preview'

    __name__ = 'document.create.preview'

    generated_report = fields.Char('Generated report', states={
            'invisible': ~Eval('generated_report')})
    party = fields.Many2One('party.party', 'Party',
        states={'invisible': True})
    email = fields.Many2One('party.contact_mechanism', 'eMail', domain=[
            ('party', '=', Eval('party')),
            ('type', '=', 'email')], depends=['party'])
    filename = fields.Char('Filename', states={'invisible': True})
    exact_name = fields.Char('Exact Name', states={'invisible': True})


class DocumentCreateAttach(model.CoopView):
    'Document Create Attach'

    __name__ = 'document.create.attach'

    attachment = fields.Binary('Data File', filename='name')
    name = fields.Char('Filename')


class DocumentCreate(Wizard):
    __name__ = 'document.create'

    start_state = 'select_model'
    mail = StateAction('offered_insurance.generate_file_report')
    post_generation = StateTransition()
    select_model = StateView('document.create.select',
        'offered_insurance.document_create_select_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Preview', 'preview_document', 'tryton-go-next'),
            ])
    preview_document = StateView('document.create.preview',
        'offered_insurance.document_create_preview_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'select_model', 'tryton-go-previous'),
            Button('Mail', 'mail', 'tryton-go-next', states={
                    'readonly': ~Eval('email')}),
            ])
    attach = StateView('document.create.attach',
        'offered_insurance.document_create_attach_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Complete', 'post_generation', 'tryton-ok')])
    attach_to_contact = StateTransition()

    @classmethod
    def __setup__(cls):
        super(DocumentCreate, cls).__setup__()
        try:
            shutil.rmtree(CONFIG['server_shared_folder'])
        except:
            pass

    def default_select_model(self, fields):
        result = utils.set_state_view_defaults(self, 'select_model')
        if result['id']:
            return result
        ActiveModel = Pool().get(Transaction().context.get('active_model'))
        instance = ActiveModel(Transaction().context.get('active_id'))
        if not instance:
            return {}
        letters = []
        has_selection = True
        for elem in instance.get_available_doc_templates():
            letters.append({
                'doc_template': elem.id,
                'selected': has_selection})
            has_selection = False
        if letters:
            result['models'] = letters
        result['party'] = instance.get_contact().id
        if instance.get_contact().addresses:
            result['good_address'] = instance.get_contact().addresses[0].id
        return result

    def default_preview_document(self, fields):
        pool = Pool()
        ReportModel = pool.get('document.generate.report', type='report')
        ContactMechanism = pool.get('party.contact_mechanism')
        ActiveModel = pool.get(Transaction().context.get('active_model'))
        instance = ActiveModel(Transaction().context.get('active_id'))
        sender = instance.get_sender()
        sender_address = instance.get_sender_address()
        _, result, _, exact_name = ReportModel.execute(
            [Transaction().context.get('active_id')], {
                'id': Transaction().context.get('active_id'),
                'ids': Transaction().context.get('active_ids'),
                'model': Transaction().context.get('active_model'),
                'doc_template': self.select_model.get_active_model(),
                'party': self.select_model.party.id,
                'address': self.select_model.good_address.id,
                'sender': sender.id if sender else None,
                'sender_address': sender_address.id if sender_address
                else None,
                })
        filename = coop_string.remove_invalid_char(exact_name)
        max_tries = MAX_TMP_TRIES
        while max_tries > 0:
            # Loop until we find an unused folder id
            tmp_directory = utils.id_generator()
            server_tmp_directory = os.path.join(CONFIG['server_shared_folder'],
                tmp_directory)
            try:
                os.makedirs(server_tmp_directory)
                break
            except:
                pass
            max_tries -= 1
        if max_tries == 0:
            raise Exception('Could not create tmp_directory in %s' %
                CONFIG['server_shared_folder'])
        server_filename = os.path.join(server_tmp_directory, '%s.odt' %
            filename)
        client_filename = os.path.join(CONFIG['client_shared_folder'],
            tmp_directory, '%s.odt' % filename)
        with open(server_filename, 'w') as f:
            f.write(result)
        result = {
            'generated_report': client_filename,
            'party': self.select_model.party.id,
            'filename': server_filename,
            'exact_name': exact_name,
            }
        email = ContactMechanism.search([
                ('party', '=', self.select_model.party.id),
                ('type', '=', 'email'),
                ])
        if not email:
            return result
        result['email'] = email[0].id
        return result

    def do_mail(self, action):
        DocumentTemplate = Pool().get('document.template')
        selected_model = DocumentTemplate(self.select_model.get_active_model())
        action['email_print'] = True
        action['email'] = {
            'to': self.preview_document.email.value,
            'subject': selected_model.mail_subject,
            'body': selected_model.mail_body}
        return action, {
            'filename': self.preview_document.exact_name,
            'filepath': self.preview_document.filename,
            }

    def transition_mail(self):
        return 'attach'

    def default_attach(self, fields):
        result = {'name': self.preview_document.exact_name}
        with open(self.preview_document.filename, 'r') as f:
            result['attachment'] = buffer(f.read())
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
        contact.title = self.select_model.get_active_model(False).name
        contact.for_object_ref = good_obj.get_object_for_contact()
        if (hasattr(self, 'attach') and self.attach):
            if self.preview_document.generated_report:
                Attachment = Pool().get('ir.attachment')
                attachment = Attachment()
                attachment.resource = contact.for_object_ref
                with open(self.preview_document.generated_report, 'r') as f:
                    attachment.data = buffer(f.read())
                attachment.name = self.attach.name
                attachment.save()
                contact.attachment = attachment
        contact.save()
        return 'end'


class DocumentReceiveRequest(model.CoopView):
    'Document Receive Request'

    __name__ = 'document.receive.request'

    kind = fields.Selection([('', '')], 'Kind')
    value = fields.Char('Value')
    request = fields.Many2One('document.request', 'Request',
        states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(DocumentReceiveRequest, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        idx = 0
        cls.kind.selection = [('', '')]
        for k, v in cls.allowed_values().iteritems():
            cls.kind.selection.append((k, v[0]))
            tmp = fields.Many2One(
                k, v[0],
                states={'invisible': Eval('kind') != k},
                depends=['kind', 'value'])
            setattr(cls, 'tmp_%s' % idx, tmp)

            def on_change_tmp(self, name=''):
                if not (hasattr(self, name) and getattr(self, name)):
                    return {}

                relation = getattr(self, name)
                if not (hasattr(relation, 'documents') and relation.documents):
                    return {'value': utils.convert_to_reference(
                        getattr(self, name))}
                return {'request': relation.documents[0].id}
            # Hack to fix http://bugs.python.org/issue3445
            tmp_function = functools.partial(on_change_tmp,
                name='tmp_%s' % idx)
            tmp_function.__module__ = on_change_tmp.__module__
            tmp_function.__name__ = on_change_tmp.__name__
            setattr(cls, 'on_change_tmp_%s' % idx, fields.depends(
                    'request', 'tmp_%s' % idx, 'kind')(tmp_function))
            idx += 1

    @classmethod
    def allowed_values(cls):
        return {}

    @fields.depends('kind')
    def on_change_kind(self):
        result = {}
        for k, v in self._fields.iteritems():
            if not k.startswith('tmp_'):
                continue
            result[k] = None
        return result

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        result = super(DocumentReceiveRequest,
            cls).fields_view_get(view_id, view_type)
        request_finder = Pool().get('ir.model').search([
                ('model', '=', cls.__name__)])[0]
        fields = ['kind', 'value', 'request']
        xml = '<?xml version="1.0"?>'
        xml += '<form string="%s">' % request_finder.name
        xml += '<label name="kind" xalign="0" colspan="1"/>'
        xml += '<field name="kind" colspan="3"/>'
        xml += '<field name="value" invisible="1"/>'
        xml += '<newline/>'
        xml += '<field name="request"/>'
        for k, v in cls._fields.iteritems():
            if not k.startswith('tmp_'):
                continue
            xml += '<newline/>'
            xml += '<label name="%s" colspan="1"/>' % k
            xml += '<field name="%s" colspan="3"/>' % k
            fields.append(k)
        xml += '</form>'
        result['arch'] = xml
        result['fields'] = cls.fields_get(fields_names=fields)
        return result


class DocumentReceiveAttach(model.CoopView):
    'Document Receive Attach'

    __name__ = 'document.receive.attach'

    attachments = fields.One2Many('ir.attachment', '', 'Attachments',
        context={'resource': Eval('resource')})
    resource = fields.Char('Resource', states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(DocumentReceiveAttach, cls).__setup__()
        cls._error_messages.update({
            'ident_name': 'Duplicate name on attachments : %s'})

    @fields.depends('attachments', 'resource')
    def on_change_attachments(self):
        if not (hasattr(self, 'attachments') and self.attachments):
            return {}
        codes = {}
        for att in self.attachments:
            if not att.resource in codes:
                codes[att.resource] = set()
            if att.name in codes[att.resource]:
                self.raise_user_error('ident_name', att.name)
            codes[att.resource].add(att.name)
        return {}


class DocumentReceiveSetRequests(model.CoopView):
    'Document Receive Set Requests'

    __name__ = 'document.receive.set_requests'

    documents = fields.One2Many('document.request', '', 'Documents', size=1)


class DocumentReceive(Wizard):
    'Document Receive'

    __name__ = 'document.receive'

    start_state = 'start'
    start = StateTransition()
    select_instance = StateView('document.receive.request',
        'offered_insurance.document_receive_request_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'attachment_setter', 'tryton-ok')])
    attachment_setter = StateView('document.receive.attach',
        'offered_insurance.document_receive_attach_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'only_store', 'tryton-go-next')])
    only_store = StateTransition()
    store_attachments = StateTransition()
    store_and_reconcile = StateTransition()
    input_document = StateView('document.receive.set_requests',
        'offered_insurance.document_receive_set_requests_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Complete', 'notify_request', 'tryton-ok')])
    notify_request = StateTransition()
    try_to_go_forward = StateTransition()

    @classmethod
    def __setup__(cls):
        super(DocumentReceive, cls).__setup__()
        cls._error_messages.update({
                'no_document_request_found': 'No document request found for \
this object'})

    def default_select_instance(self, name):
        if not(Transaction().context.get('active_model', 'z') in [
                k[0] for k in self.select_instance._fields['kind'].selection]):
            return {}

        GoodModel = Pool().get(Transaction().context.get('active_model'))
        good_id = Transaction().context.get('active_id')

        result = {'kind': Transaction().context.get('active_model')}
        for key, field in self.select_instance._fields.iteritems():
            if not key.startswith('tmp_'):
                continue
            if field.model_name == Transaction().context.get('active_model'):
                result[key] = Transaction().context.get('active_id')
                try:
                    result['request'] = GoodModel(good_id).documents[0].id
                except:
                    self.raise_user_error('no_document_request_found')
                break

        return result

    def transition_start(self):
        if Transaction().context.get('active_model', '') == 'ir.ui.menu':
            return 'select_instance'

        GoodModel = Pool().get(Transaction().context.get('active_model'))
        good_id = Transaction().context.get('active_id')

        self.select_instance.kind = Transaction().context.get('active_model')
        for key, field in self.select_instance._fields.iteritems():
            if not key.startswith('tmp_'):
                continue
            if field.model_name == Transaction().context.get('active_model'):
                setattr(
                    self.select_instance, key,
                    Transaction().context.get('active_id'))
                try:
                    self.select_instance.request = \
                        GoodModel(good_id).documents[0].id
                except:
                    self.raise_user_error('no_document_request_found')
                break

        return 'attachment_setter'

    def default_attachment_setter(self, name):
        Attachment = Pool().get('ir.attachment')
        if not (hasattr(self.select_instance, 'request') and
                self.select_instance.request):
            return {'resource': self.select_instance.value}
        good_obj = self.select_instance.request.needed_by
        good_obj = utils.convert_to_reference(good_obj)
        return {
            'resource': good_obj,
            'attachments': [att.id for att in Attachment.search(
                [
                    ('resource', '=', good_obj),
                ])]}

    def default_input_document(self, name):
        return {'documents': [self.select_instance.request.id]}

    def transition_only_store(self):
        if (hasattr(self.select_instance, 'request') and
                self.select_instance.request):
            return 'store_and_reconcile'
        else:
            return 'store_attachments'

    def update_attachments(self, resource):
        Attachment = Pool().get('ir.attachment')
        previous = Attachment.search([('resource', '=', resource)])
        current = [k.id for k in self.attachment_setter.attachments]
        with Transaction().set_context(_force_access=True):
            for prev_att in previous:
                if prev_att.id not in current:
                    prev_att.delete([prev_att])
            for att in self.attachment_setter.attachments:
                if isinstance(att.data, int):
                    continue
                att.resource = resource
                att.save()

    def transition_store_attachments(self):
        resource = self.select_instance.value
        if resource:
            self.update_attachments(resource)
        return 'end'

    def transition_store_and_reconcile(self):
        resource = self.select_instance.request.needed_by
        resource = utils.convert_to_reference(resource)
        self.update_attachments(resource)
        return 'input_document'

    def transition_notify_request(self):
        for doc in self.input_document.documents[0].documents:
            doc.save()
        self.input_document.documents[0].save()
        if self.input_document.documents[0].is_complete:
            self.input_document.documents[0].notify_completed()

        return 'try_to_go_forward'

    def transition_try_to_go_forward(self):
        # try:
            # obj = self.select_instance.request.needed_by
            # obj.build_instruction_method('next')([obj])
        # except AttributeError:
            # pass

        return 'end'


class DocumentRequestBatch(BatchRoot):
    'Document Request Batch Definition'

    __name__ = 'document.request.batch'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'document.request'

    @classmethod
    def get_batch_search_model(cls):
        return 'document.request.line'

    @classmethod
    def get_batch_field(cls):
        return 'request'

    @classmethod
    def get_batch_ordering(cls):
        return [('request', 'ASC')]

    @classmethod
    def get_batch_name(cls):
        return 'Document Request Batch'

    @classmethod
    def get_batch_domain(cls):
        return [
            ('reception_date', '=', None),
            [
                'OR',
                ('send_date', '=', None),
                ('send_date', '<=', coop_date.add_month(utils.today(), -3))]]

    @classmethod
    def execute(cls, objects, ids, logger):
        DocumentCreate = Pool().get(
            'document.create', type='wizard')
        for cur_object in objects:
            with Transaction().set_context(
                    active_model=cur_object.__name__, active_id=cur_object.id):
                wizard_id, _, _ = DocumentCreate.create()
                wizard = DocumentCreate(wizard_id)
                data = wizard.execute(wizard_id, {}, 'select_model')
                data = wizard.execute(wizard_id, {
                    'select_model': data['view']['defaults']}, 'generate')
                report_def, data = data['actions'][0]
                Report = Pool().get(report_def['report_name'], type='report')
                format, buffer, _, name = Report.execute([data['id']], data)
                cls.write_batch_output(format, buffer, name)
                wizard.execute(wizard_id, {}, 'post_generation')
                logger.info(
                    'Treated Request for %s' % cur_object.get_rec_name(None))
