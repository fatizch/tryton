#-*- coding:utf-8 -*-
import copy

from trytond.model import fields, ModelSQL
from trytond.pool import Pool, PoolMeta
from trytond.report import Report
from trytond.ir import Attachment

from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.modules.coop_utils import model, utils
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_SIMPLE

__all__ = [
    'DocumentDesc',
    'DocumentRule',
    'DocumentRuleRelation',
    'Document',
    'DocumentRequest',
    'DocumentRequestReport',
    'LetterModel',
    'LetterVersion',
    'Printable',
    'Model',
]


class LetterModel(model.CoopSQL, model.CoopView):
    'Letter Model'

    __name__ = 'ins_product.letter_model'

    name = fields.Char(
        'Name',
        required=True,
    )

    on_model = fields.Many2One(
        'ir.model',
        'Model',
        domain=[('printable', '=', True)],
        required=True,
    )

    code = fields.Char(
        'Code',
        required=True,
    )

    versions = fields.One2Many(
        'ins_product.letter_version',
        'resource',
        'Versions',
    )

    kind = fields.Selection(
        [
            ('', ''),
            ('doc_request', 'Document Request'),
        ],
        'name',
    )

    def get_good_version(self, date, language):
        for version in self.versions:
            if not version.language == language:
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

    start_date = fields.Date(
        'Start date',
    )

    end_date = fields.Date(
        'End date',
    )

    language = fields.Many2One(
        'ir.lang',
        'Language',
    )

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


class Model():
    'Model'

    __metaclass__ = PoolMeta

    __name__ = 'ir.model'

    printable = fields.Boolean(
        'Printable',
    )


class Printable(ModelSQL):
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


class DocumentDesc(model.CoopSQL, model.CoopView):
    'Document Descriptor'

    __name__ = 'ins_product.document_desc'

    code = fields.Char('Code', required=True)

    name = fields.Char('Name', required=True)

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
        ],
        'Kind',
    )

    documents = fields.Many2Many(
        'ins_product.document-rule-relation',
        'rule',
        'document',
        'Documents',
        states={
            'invisible': STATE_SIMPLE,
        },
    )

    def give_me_documents(self, args):
        if self.config_kind == 'simple':
            return self.documents, []

        if not self.rule:
            return [], []

        try:
            res, mess, errs = self.rule.compute(args)
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

    rule = fields.Many2One(
        'ins_product.document_rule',
        'Rule',
        ondelete='CASCADE',
    )

    document = fields.Many2One(
        'ins_product.document_desc',
        'Document',
        ondelete='RESTRICT',
    )


class Document(model.CoopSQL, model.CoopView):
    'Document'

    __name__ = 'ins_product.document'

    document_desc = fields.Many2One(
        'ins_product.document_desc',
        'Document Definition',
        required=True,
    )

    for_object = fields.Reference(
        'Needed For',
        [('', '')],
        states={
            'readonly': ~~Eval('for_object')
        },
    )

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
    )

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


class DocumentRequest(model.CoopSQL, model.CoopView, Printable):
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

    contact_party = fields.Function(
        fields.Many2One(
            'party.party',
            'Contact Party',
        ),
        'get_contact_party',
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
            'create_document_request': {}})

    def get_request_date(self):
        return utils.today()

    def on_change_with_request_description(self, name=None):
        return 'Document Request for %s' % self.needed_by.get_rec_name(name)

    def get_contact_party(self, name):
        if not (hasattr(self, 'needed_by') and self.needed_by):
            return None

        try:
            return self.needed_by.get_main_contact().id
        except AttributeError:
            return None

    def on_change_with_needed_by_str(self, name=None):
        if not (hasattr(self, 'needed_by') and self.needed_by):
            return ''

        return utils.convert_to_reference(self.needed_by)

    def on_change_with_is_complete(self, name=None):
        if not (hasattr(self, 'documents') and self.documents):
            return False

        for doc in self.documents:
            if not doc.received:
                return False

        return True

    def on_change_documents(self):
        return {'is_complete': self.on_change_with_is_complete()}

    def on_change_is_complete(self):
        if not (hasattr(self, 'is_complete') or not self.is_complete):
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

    @classmethod
    @model.CoopView.button_action('insurance_product.report_document_request')
    def create_document_request(cls, requests):
        pass

    def get_waiting_documents(self):
        return len([doc for doc in self.documents if not doc.received])


class DocumentRequestReport(Report):
    __name__ = 'ins_product.document_request'
