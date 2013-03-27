#-*- coding:utf-8 -*-
import copy
import StringIO
import functools

from trytond.model import Model
from trytond.pool import Pool, PoolMeta
from trytond.wizard import Wizard, StateAction, StateView, Button
from trytond.wizard import StateTransition
from trytond.report import Report
from trytond.ir import Attachment

from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.modules.coop_utils import fields, model, utils, coop_string
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_SIMPLE

__all__ = [
    'NoTargetCheckAttachment',
    'DocumentDesc',
    'DocumentRule',
    'DocumentRuleRelation',
    'Document',
    'DocumentRequest',
    'LetterModel',
    'LetterVersion',
    'Printable',
    'OverridenModel',
    'LetterModelDisplayer',
    'LetterModelSelection',
    'LetterReport',
    'LetterGeneration',
    'RequestFinder',
    'AttachmentSetter',
    'DocumentRequestDisplayer',
    'ReceiveDocuments',
    'AttachmentCreation',
]


class LetterModel(model.CoopSQL, model.CoopView):
    'Letter Model'

    __name__ = 'ins_product.letter_model'

    name = fields.Char('Name', required=True, translate=True)
    on_model = fields.Many2One('ir.model', 'Model',
        domain=[('printable', '=', True)], required=True)
    code = fields.Char('Code', required=True)
    versions = fields.One2Many('ins_product.letter_version',
        'resource', 'Versions')
    kind = fields.Selection([
            ('', ''),
            ('doc_request', 'Document Request'),
        ], 'name')

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


class LetterVersion(Attachment):
    'Letter Version'

    __name__ = 'ins_product.letter_version'

    start_date = fields.Date('Start date', required=True)
    end_date = fields.Date('End date')
    language = fields.Many2One('ir.lang', 'Language', required=True)

    @classmethod
    def __setup__(cls):
        super(LetterVersion, cls).__setup__()

        cls.type = copy.copy(cls.type)
        cls.type.states = {'readonly': True}

        cls.resource = copy.copy(cls.resource)
        cls.resource.selection = [(
            'ins_product.letter_model', 'Letter Model')]

    @classmethod
    def default_type(cls):
        return 'data'


class OverridenModel():
    'Model'

    __name__ = 'ir.model'
    __metaclass__ = PoolMeta

    printable = fields.Boolean('Printable')


class Printable(Model):
    @classmethod
    def __register__(cls, module_name):
        # We need to store the fact that this class is a Printable class in the
        # database.
        super(Printable, cls).__register__(module_name)

        GoodModel = Pool().get('ir.model')

        good_model, = GoodModel.search([
            ('model', '=', cls.__name__)], limit=1)

        # Basically, that is just setting 'is_workflow' to True
        good_model.printable = True

        good_model.save()

    @classmethod
    @model.CoopView.button_action('insurance_product.letter_generation_wizard')
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

    def get_available_letter_models(self, kind=None):
        LetterModel = Pool().get('ins_product.letter_model')

        domain = [
            ('on_model.model', '=', self.__name__),
            ['OR',
                ('kind', '=', kind or self.get_letter_model_kind()),
                ('kind', '=', '')]]

        return LetterModel.search(domain)

    def get_letter_model_kind(self):
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
            return None
        return StringIO.StringIO(str(good_logo))

    def get_sender(self):
        return self.get_object_for_contact().get_sender()

    def get_sender_address(self):
        sender = self.get_sender()
        if not sender or not sender.addresses:
            return None
        return sender.addresses[0]


class DocumentDesc(model.CoopSQL, model.CoopView):
    'Document Descriptor'

    __name__ = 'ins_product.document_desc'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


class DocumentRule(BusinessRuleRoot, model.CoopSQL):
    'Document Managing Rule'

    __name__ = 'ins_product.document_rule'

    kind = fields.Selection(
        [
            ('main', 'Main'),
            ('sub', 'Sub Elem'),
            ('loss', 'Loss'),
            ('', ''),
        ], 'Kind')
    documents = fields.Many2Many('ins_product.document-rule-relation',
        'rule', 'document', 'Documents',
        states={'invisible': STATE_SIMPLE})

    def give_me_documents(self, args):
        if self.config_kind == 'simple':
            return self.documents, []
        if not self.rule:
            return [], []
        try:
            res, mess, errs = utils.execute_rule(self, self.rule, args)
        except Exception:
            return [], ['Invalid rule']
        try:
            result = utils.get_those_objects(
                'ins_product.document', [
                    ('code', 'in', res)])
            return result, []
        except:
            return [], ['Invalid documents']

    @classmethod
    def default_kind(cls):
        return Transaction().context.get('doc_rule_kind', None)


class DocumentRuleRelation(model.CoopSQL):
    'Relation between rule and document'

    __name__ = 'ins_product.document-rule-relation'

    rule = fields.Many2One('ins_product.document_rule',
        'Rule', ondelete='CASCADE')
    document = fields.Many2One('ins_product.document_desc',
        'Document', ondelete='RESTRICT')


class Document(model.CoopSQL, model.CoopView):
    'Document'

    __name__ = 'ins_product.document'

    document_desc = fields.Many2One('ins_product.document_desc',
        'Document Definition', required=True)
    for_object = fields.Reference('Needed For',
        [('', '')],
        states={'readonly': ~~Eval('for_object')})

    send_date = fields.Date(
        'Send Date',
    )

    reception_date = fields.Date(
        'Reception Date',
        on_change_with=['attachment', 'reception_date'],
    )

    request_date = fields.Date(
        'Request Date',
        states={
            'readonly': True
        },
    )

    received = fields.Function(
        fields.Boolean(
            'Received',
            depends=['attachment', 'reception_date'],
            on_change_with=['reception_date'],
            on_change=['received', 'reception_date'],
        ),
        'on_change_with_received',
        'setter_void',
    )

    request = fields.Many2One(
        'ins_product.document_request',
        'Document Request',
        ondelete='CASCADE',
    )

    attachment = fields.Many2One(
        'ir.attachment',
        'Attachment',
        domain=[
            ('resource', '=', Eval('_parent_request', {}).get(
                'needed_by_str'))],
        on_change=['attachment', 'reception_date', 'received'],
    )

    def on_change_attachment(self):
        if not (hasattr(self, 'attachment') and self.attachment):
            return {}

        return {
            'received': True,
            'reception_date': (
                hasattr(self, 'reception_date') and
                self.reception_date) or utils.today()}

    def on_change_with_received(self, name=None):
        if not (hasattr(self, 'reception_date') and self.reception_date):
            return False
        else:
            return True

    def on_change_received(self):
        if (hasattr(self, 'received') and self.received):
            if (hasattr(self, 'reception_date') and self.reception_date):
                return {}
            else:
                return {'reception_date': utils.today()}
        else:
            return {'reception_date': None}

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

    __name__ = 'ins_product.document_request'

    needed_by = fields.Reference(
        'Requested for',
        [('', '')],
    )

    documents = fields.One2Many(
        'ins_product.document',
        'request',
        'Documents',
        depends=['needed_by_str'],
        on_change=['documents', 'is_complete'],
        context={'request_owner': Eval('needed_by_str')},
    )

    is_complete = fields.Function(
        fields.Boolean(
            'Is Complete',
            depends=['documents'],
            on_change_with=['documents'],
            on_change=['documents', 'is_complete'],
            states={
                'readonly': ~~Eval('is_complete')
            },
        ),
        'on_change_with_is_complete',
        'setter_void',
    )

    needed_by_str = fields.Function(
        fields.Char(
            'Master as String',
            on_change_with=['needed_by'],
            depends=['needed_by'],
        ),
        'on_change_with_needed_by_str',
    )

    request_description = fields.Function(
        fields.Char(
            'Request Description',
            depends=['needed_by'],
            on_change_with=['needed_by'],
        ),
        'on_change_with_request_description',
    )

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()

        cls._buttons.update({
            'generic_send_letter': {}})

    def get_request_date(self):
        return utils.today()

    def on_change_with_request_description(self, name=None):
        return 'Document Request for %s' % self.needed_by.get_rec_name(name)

    def get_contact(self, name=None):
        if not (hasattr(self, 'needed_by') and self.needed_by):
            return None

        try:
            return self.needed_by.get_main_contact()
        except AttributeError:
            return None

    def on_change_with_needed_by_str(self, name=None):
        if not (hasattr(self, 'needed_by') and self.needed_by):
            return ''

        return utils.convert_to_reference(self.needed_by)

    def on_change_with_is_complete(self, name=None):
        if not (hasattr(self, 'documents') and self.documents):
            return True

        for doc in self.documents:
            if not doc.received:
                return False

        return True

    def on_change_documents(self):
        return {'is_complete': self.on_change_with_is_complete()}

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
        Document = Pool().get('ins_product.document')
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

        Document = Pool().get('ins_product.document')

        Document.delete(to_del)

    def get_waiting_documents(self):
        return len([doc for doc in self.documents if not doc.received])

    def post_generation(self):
        for document in self.documents:
            if document.send_date is None and not document.received:
                document.send_date = utils.today()
                document.save()

    def notify_completed(self):
        pass

    def get_letter_model_kind(self):
        return 'doc_request'

    def get_object_for_contact(self):
        return self.needed_by

    def get_rec_name(self, name):
        return self.needed_by.get_rec_name(name)


class LetterModelDisplayer(model.CoopView):
    'Letter Model Displayer'

    __name__ = 'ins_product.letter_model_displayer'

    letter_model = fields.Many2One(
        'ins_product.letter_model',
        'Letter Model',
    )

    selected = fields.Boolean(
        'Selected',
    )


class LetterModelSelection(model.CoopView):
    'Letter Model Selection'

    __name__ = 'ins_product.letter_model_selection'

    models = fields.One2Many(
        'ins_product.letter_model_displayer',
        '',
        'Models',
    )

    good_address = fields.Many2One(
        'party.address',
        'Mail Address',
        domain=[('party', '=', Eval('party'))],
        depends=['party'],
        required=True,
    )

    party = fields.Many2One(
        'party.party',
        'Party',
        states={
            'invisible': True
        },
    )

    def get_active_model(self, id_only=True):
        for elem in self.models:
            if elem.selected:
                if id_only:
                    return elem.letter_model.id
                else:
                    return elem.letter_model


class LetterReport(Report):
    __name__ = 'ins_product.letter_report'

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
        records = cls._get_records(
            ids, data['model'], data)
        LetterModel = Pool().get('ins_product.letter_model')
        good_letter = LetterModel(data['letter_model'])
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
        return (
            type, buffer(data), action_report.direct_print, filename)

    @classmethod
    def parse(cls, report, records, data, localcontext):
        localcontext['Party'] = Pool().get('party.party')(data['party'])
        localcontext['Address'] = Pool().get('party.address')(data['address'])
        try:
            localcontext['Lang'] = localcontext['Party'].lang.code
        except AttributeError:
            localcontext['Lang'] = 'en_US'
        if data['sender']:
            localcontext['Sender'] = Pool().get('party.party')(data['sender'])
        if data['sender_address']:
            localcontext['SenderAddress'] = Pool().get(
                'party.address')(data['sender_address'])
        # localcontext['Logo'] = data['logo']
        localcontext['Today'] = utils.today()
        GoodModel = Pool().get(data['model'])
        good_obj = GoodModel(data['id'])
        LetterModel = Pool().get('ins_product.letter_model')
        good_letter = LetterModel(data['letter_model'])
        report.report_content = good_letter.get_good_version(
            utils.today(), good_obj.get_lang()).data
        return super(LetterReport, cls).parse(
            report, records, data, localcontext)


class AttachmentCreation(model.CoopView):
    'Attachment Creation'

    __name__ = 'ins_product.attach_letter'

    attachment = fields.Binary('Data File', filename='name')
    name = fields.Char('Filename')


class LetterGeneration(Wizard):
    __name__ = 'ins_product.letter_creation_wizard'

    class SpecialStateAction(StateAction):

        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            Action = Pool().get('ir.action')
            ActionReport = Pool().get('ir.action.report')
            good_report, = ActionReport.search([
                ('report_name', '=', 'ins_product.letter_report')
                ('model', '=', Transaction().context.get('active_model')),
            ], limit=1)
            return Action.get_action_values(
                'ir.action.report', good_report.id)

    start_state = 'select_model'

    generate = StateAction('insurance_product.letter_generation_report')

    post_generation = StateTransition()

    select_model = StateView(
        'ins_product.letter_model_selection',
        'insurance_product.letter_model_selection_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate', 'generate', 'tryton-ok'),
            Button('Attach', 'attach', 'tryton-go-next'),
            Button('Complete', 'post_generation', 'tryton-ok')])

    attach = StateView(
        'ins_product.attach_letter',
        'insurance_product.attach_letter_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Attach', 'post_generation', 'tryton-ok')])

    attach_to_contact = StateTransition()

    def transition_generate(self):
        return 'select_model'

    def do_generate(self, action):
        ActiveModel = Pool().get(Transaction().context.get('active_model'))
        good_model = ActiveModel(Transaction().context.get('active_id'))
        sender = good_model.get_sender()
        sender_address = good_model.get_sender_address()
        # logo = good_model.format_logo()

        return action, {
            'id': Transaction().context.get('active_id'),
            'ids': Transaction().context.get('active_ids'),
            'model': Transaction().context.get('active_model'),
            'letter_model': self.select_model.get_active_model(),
            'party': self.select_model.party.id,
            'address': self.select_model.good_address.id,
            'sender': sender.id if sender else None,
            'sender_address': sender_address.id if sender_address else None,
            # 'logo': logo,
        }

    def default_select_model(self, fields):
        ActiveModel = Pool().get(Transaction().context.get('active_model'))
        good_model = ActiveModel(Transaction().context.get('active_id'))

        if not good_model:
            return {}

        letters = []
        has_selection = True
        for elem in good_model.get_available_letter_models():
            letters.append({
                'letter_model': elem.id,
                'selected': has_selection})
            has_selection = False

        if letters:
            result = {'models': letters}
        else:
            result = {}

        result['party'] = good_model.get_contact().id
        if good_model.get_contact().addresses:
            result['good_address'] = good_model.get_contact().addresses[0].id

        return result

    def transition_post_generation(self):
        GoodModel = Pool().get(Transaction().context.get('active_model'))
        good_obj = GoodModel(Transaction().context.get('active_id'))
        good_obj.post_generation()

        ContactHistory = Pool().get('party.contact_history')
        contact = ContactHistory()
        contact.party = good_obj.get_contact()
        contact.media = 'mail'
        contact.address = self.select_model.good_address
        contact.title = self.select_model.get_active_model(False).name
        contact.for_object_ref = good_obj.get_object_for_contact()
        if (hasattr(self, 'attach') and self.attach):
            if self.attach.attachment:
                Attachment = Pool().get('ir.attachment')
                attachment = Attachment()
                attachment.resource = contact.for_object_ref
                attachment.data = self.attach.attachment
                attachment.name = self.attach.name
                attachment.save()
                contact.attachment = attachment
        contact.save()
        return 'end'


class RequestFinder(model.CoopView):
    'Request Finder'

    __name__ = 'ins_product.request_finder'

    kind = fields.Selection(
        [
            ('', '')
        ],
        'Kind',
        on_change=['kind'],
    )

    value = fields.Char(
        'Value',
    )

    request = fields.Many2One(
        'ins_product.document_request',
        'Request',
        states={
            'invisible': True
        })

    @classmethod
    def __setup__(cls):
        super(RequestFinder, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        idx = 0
        for k, v in cls.allowed_values().iteritems():
            cls.kind.selection.append((k, v[0]))
            tmp = fields.Many2One(
                k, v[0],
                states={'invisible': Eval('kind') != k},
                depends=['kind', 'value'],
                on_change=['request', 'tmp_%s' % idx, 'kind'])
            setattr(cls, 'tmp_%s' % idx, tmp)

            def on_change_tmp(self, name=''):
                if not (hasattr(self, name) and getattr(self, name)):
                    return {}

                relation = getattr(self, name)
                if not (hasattr(relation, 'documents') and relation.documents):
                    return {'value': utils.convert_to_reference(
                        getattr(self, name))}

                return {'request': relation.documents[0].id}

            setattr(cls, 'on_change_tmp_%s' % idx, functools.partial(
                on_change_tmp, name='tmp_%s' % idx))
            idx += 1

    @classmethod
    def allowed_values(cls):
        return {}

    def on_change_kind(self):
        result = {}
        for k, v in self._fields.iteritems():
            if not k.startswith('tmp_'):
                continue

            result[k] = None
        return result

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        result = super(RequestFinder, cls).fields_view_get(view_id, view_type)

        fields = ['kind', 'value', 'request']

        xml = '<?xml version="1.0"?>'
        xml += '<form string="%s">' % cls.__name__
        xml += '<label name="kind" xalign="0"/>'
        xml += '<field name="kind" colspan="3"/>'
        xml += '<field name="value" invisible="1"/>'
        xml += '<newline/>'
        xml += '<field name="request"/>'

        for k, v in cls._fields.iteritems():
            if not k.startswith('tmp_'):
                continue

            xml += '<newline/>'
            xml += '<field name="%s" colspan="4"/>' % k

            fields.append(k)

        xml += '</form>'

        result['arch'] = xml
        result['fields'] = cls.fields_get(fields_names=fields)

        return result


class NoTargetCheckAttachment():
    'Attachment'

    __metaclass__ = PoolMeta
    __name__ = 'ir.attachment'

    @classmethod
    def check_access(cls, ids, mode='read'):
        if '_force_access' in Transaction().context:
            return
        super(NoTargetCheckAttachment, cls).check_access(ids, mode)


class AttachmentSetter(model.CoopView):
    'Attachment Setter'

    __name__ = 'ins_product.attachment_setter'

    attachments = fields.One2Many(
        'ir.attachment', '', 'Attachments',
        context={'resource': Eval('resource')},
        on_change=['attachments', 'resource'],
    )
    resource = fields.Char('Resource', states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(AttachmentSetter, cls).__setup__()
        cls._error_messages.update({
            'ident_name': 'Duplicate name on attachments : %s'})

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


class DocumentRequestDisplayer(model.CoopView):
    'Document Request Displayer'

    __name__ = 'ins_product.document_request_displayer'

    documents = fields.One2Many(
        'ins_product.document_request',
        '',
        'Documents',
        size=1,
    )


class ReceiveDocuments(Wizard):
    'Receive Documents Wizard'

    __name__ = 'ins_product.receive_document_wizard'

    start_state = 'start'
    start = StateTransition()
    select_instance = StateView(
        'ins_product.request_finder',
        'insurance_product.request_finder_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'attachment_setter', 'tryton-ok')])
    attachment_setter = StateView(
        'ins_product.attachment_setter',
        'insurance_product.attachment_setter_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'only_store', 'tryton-go-next')])
    only_store = StateTransition()
    store_attachments = StateTransition()
    store_and_reconcile = StateTransition()
    input_document = StateView(
        'ins_product.document_request_displayer',
        'insurance_product.document_request_displayer_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Complete', 'notify_request', 'tryton-ok')])
    notify_request = StateTransition()
    try_to_go_forward = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ReceiveDocuments, cls).__setup__()

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
