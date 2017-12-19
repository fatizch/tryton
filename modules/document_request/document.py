# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from sql.functions import CurrentDate
from sql import Null
from sql.aggregate import Count, Sum
from sql.conditionals import Case

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond import backend
from trytond.transaction import Transaction
from trytond.cache import Cache

from trytond.modules.coog_core import fields, model, utils
from trytond.modules.report_engine import Printable
from trytond.modules.rule_engine import get_rule_mixin


__all__ = [
    'DocumentDescription',
    'DocumentRequestLine',
    'DocumentRequest',
    'DocumentReception',
    'ReceiveDocument',
    'ReattachDocument',
    'ReceiveDocumentLine',
    ]


class DocumentDescription:
    __metaclass__ = PoolMeta
    __name__ = 'document.description'

    reception_requires_attachment = fields.Boolean(
        'Reception Requires Attachment', help='If checked, the attachments'
        'will be required to mark the document request lines as "received"')


class DocumentRequestLine(model.CoogSQL, model.CoogView):
    'Document Request Line'

    __name__ = 'document.request.line'

    document_desc = fields.Many2One('document.description',
        'Document Definition', required=True, ondelete='RESTRICT')
    for_object = fields.Reference('Needed For', selection='models_get',
        states={'readonly': ~~Eval('for_object')}, required=True, select=True,
        help='References the object for which the document is asked.')
    send_date = fields.Date('Send Date')
    reception_date = fields.Date('Reception Date')
    first_reception_date = fields.Date('First Reception Date')
    request_date = fields.Date('Request Date', states={'readonly': True})
    received = fields.Function(
        fields.Boolean('Received',
            states={'readonly': ~Eval('allow_force_receive')},
            depends=['allow_force_receive'],
            ),
        getter='on_change_with_received', setter='setter_void',
        searcher='search_received')
    request = fields.Many2One('document.request', 'Document Request',
        ondelete='CASCADE', select=True)
    attachment = fields.Many2One('ir.attachment', 'Attachment',
        domain=[('resource', '=', Eval('for_object')),
            ('document_desc', '=', Eval('document_desc'))],
        depends=['for_object', 'document_desc'], ondelete='RESTRICT')
    attachment_name = fields.Function(fields.Char('Attachment Name',
            depends=['attachment']),
        'get_attachment_info')
    attachment_data = fields.Function(
        fields.Binary('Data', filename='attachment_name',
            depends=['attachment']),
        'get_attachment_info', 'set_attachment_data')
    matching_attachments = fields.Function(
        fields.Many2Many('ir.attachment', None, None, 'Matching Attachments'),
        'get_matching_attachments')
    blocking = fields.Boolean('Blocking', states={'readonly': True})
    last_reminder_date = fields.Date('Last Reminder Date',
        states={'invisible': True})
    reminders_sent = fields.Integer('Reminders Sent')
    details = fields.Text('Details')
    allow_force_receive = fields.Function(fields.Boolean('Force Receive'),
        'get_allow_force_receive')

    _models_get_request_line_cache = Cache('models_get_request_line')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        doc_h = TableHandler(cls, module_name)
        to_migrate = not doc_h.column_exist('last_reminder_date')
        super(DocumentRequestLine, cls).__register__(module_name)
        to_update = cls.__table__()
        if to_migrate:
            cursor.execute(*to_update.update(
                    columns=[
                        to_update.last_reminder_date,
                        to_update.reminders_sent],
                    values=[CurrentDate(), 0],
                    where=to_update.last_reminder_date == Null,
                    ))

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
        return super(DocumentRequestLine, cls).search(domain, *args, **kwargs)

    @classmethod
    def create(cls, vlist):
        # Add hook to update creation data depending on the target model. See
        # contract / claim implementation for examples
        per_target = defaultdict(list)
        for elem in vlist:
            if 'for_object' in elem:
                per_target[elem.get('for_object')].append(elem)
        cls.update_values_from_target(per_target)
        return super(DocumentRequestLine, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        # Add hook to update write data depending on the target model. See
        # contract / claim implementation for examples
        params = iter(args)
        per_target = defaultdict(list)
        for _, values in zip(params, params):
            if 'for_object' in values:
                per_target[values.get('for_object')].append(values)
        cls.update_values_from_target(per_target)
        super(DocumentRequestLine, cls).write(*args)

    @classmethod
    def update_values_from_target(cls, data_dict):
        pass

    @staticmethod
    def default_last_reminder_date():
        return utils.today()

    @staticmethod
    def default_reminders_sent():
        return 0

    @classmethod
    def update_reminder(cls, document_lines, treatment_date, increment=False):
        if not document_lines:
            return
        for doc in document_lines:
            doc.last_reminder_date = treatment_date
            if increment:
                doc.reminders_sent += 1
        cls.save(document_lines)

    @classmethod
    def for_object_models(cls):
        return []

    @classmethod
    def models_get(cls):
        models = cls._models_get_request_line_cache.get(None)
        if models:
            return models

        Model = Pool().get('ir.model')
        allowed = cls.for_object_models()
        models = sorted([(x.model, x.name) for x in Model.search(
            [('model', 'in', allowed)])],
            key=lambda x: x[1]) + [('', '')]
        cls._models_get_request_line_cache.set(None, models)
        return models

    @classmethod
    def get_default_remind_fields(cls):
        return ['received']

    @fields.depends('attachment', 'attachment_data', 'reception_date',
        'first_reception_date', 'allow_force_receive')
    def update_lines_fields(self, uncheck_receive=False):
        if self.attachment or self.attachment_data:
            if not self.reception_date and not uncheck_receive:
                self.reception_date = utils.today()
            if not self.first_reception_date:
                self.first_reception_date = self.reception_date
            if self.attachment:
                self.attachment_name = self.attachment.name
                self.attachment_data = self.attachment.data
        else:
            if self.allow_force_receive:
                if not self.first_reception_date:
                    self.first_reception_date = self.reception_date
            else:
                self.reception_date = None
                self.attachment_name = None
                self.attachment_data = None

    @fields.depends('attachment', 'reception_date', 'first_reception_date',
        'allow_force_receive', 'received')
    def on_change_reception_date(self):
        kwargs = {}
        if not self.reception_date:
            kwargs['uncheck_receive'] = True
        self.update_lines_fields(**kwargs)

    @fields.depends('attachment', 'reception_date', 'first_reception_date',
        'allow_force_receive', 'received')
    def on_change_received(self):
        if self.allow_force_receive:
            if self.received:
                self.reception_date = utils.today()
            else:
                self.reception_date = None

        kwargs = {}
        if self.allow_force_receive and not self.received:
            kwargs['uncheck_receive'] = True
        self.update_lines_fields(**kwargs)

    @fields.depends('reception_date', 'attachment', 'attachment_data',
        'allow_force_receive')
    def on_change_with_received(self, name=None):
        return bool(self.reception_date) and (
            (bool(self.attachment) or bool(self.attachment_data)) or
            self.allow_force_receive)

    @fields.depends('attachment', 'attachment_date', 'reception_date',
        'first_reception_date', 'allow_force_receive', 'received')
    def on_change_attachment(self):
        if not self.attachment:
            self.attachment_data = None
        self.update_lines_fields()

    @fields.depends('attachment', 'reception_date', 'first_reception_date',
        'allow_force_receive', 'received', 'attachment_data')
    def on_change_attachment_data(self):
        if not self.attachment_data:
            self.attachment = None
        self.update_lines_fields()

    def get_rec_name(self, name):
        return self.document_desc.name if self.document_desc else ''

    @classmethod
    def default_request_date(cls):
        return utils.today()

    @classmethod
    def default_for_object(cls):
        if 'request_owner' not in Transaction().context:
            return ''

        needed_by = Transaction().context.get('request_owner')
        the_model, the_id = needed_by.split(',')
        if the_model not in [
                k for k, v in cls._fields['for_object'].selection]:
            return ''
        return needed_by

    @classmethod
    def search_received(cls, name, domain):
        _, op, value = domain
        if value is True:
            op = '!=' if op == '=' else '='
        return [('reception_date', op, None)]

    def get_attachment_info(self, name):
        if self.attachment:
            return getattr(self.attachment, name.split('_')[1])

    @classmethod
    def set_attachment_data(cls, requests, name, value):
        Attachment = Pool().get('ir.attachment')
        attachments = []
        to_save = []
        for request in requests:
            if not request.attachment and value:
                attachment = Attachment()
                attachment.resource = request.for_object
                attachment.document_desc = request.document_desc
                attachment.data = value
                attachment.name = request.document_desc.name
                if request.matching_attachments:
                    attachment.name += '_%s' % (
                        len(request.matching_attachments) + 1)
                attachments.append(attachment)
                request.attachment = attachment
                request.received = True
                request.on_change_received()
                to_save.append(request)
            elif request.attachment and value:
                request.attachment.data = value
                attachments.append(request.attachment)
            elif request.attachment and not value:
                request.received = False
                request.on_change_received()
                request.reception_date = None
                request.attachment = None
                to_save.append(request)
        if to_save:
            cls.save(to_save)
        if attachments:
            Attachment.save(attachments)

    def get_matching_attachments(self, name):
        Attachment = Pool().get('ir.attachment')
        return [x.id for x in Attachment.search([
                    ('resource', '=', str(self.for_object)),
                    ('document_desc', '=', self.document_desc)])]

    @classmethod
    def update_and_notify_reminders(cls, to_remind_per_object,
            force_remind, event_code, treatment_date):
        pool = Pool()
        pool.get('event').notify_events(to_remind_per_object.keys(),
            event_code)
        document_lines = [x for sublist in to_remind_per_object.values()
                for x in sublist]
        cls.update_reminder(document_lines, treatment_date,
            increment=not force_remind)

    def attachment_not_required(self):
        '''
        Returns a boolean which define whether the "received" field on document
        request line can be set manually.
        This is allowed by default unless the configuration related to the
        document request does not allow it.
        '''
        # Default behavior: Allow force receive
        return not self.document_desc.reception_requires_attachment

    def get_allow_force_receive(self, name=None):
        return self.attachment_not_required()


class DocumentRequest(Printable, model.CoogSQL, model.CoogView):
    'Document Request'

    __name__ = 'document.request'

    needed_by = fields.Reference('Requested for', [('', '')], required=True,
        select=True)
    documents = fields.One2Many('document.request.line', 'request',
        'Documents', depends=['needed_by_str'],
        context={'request_owner': Eval('needed_by_str')}, delete_missing=True,
        target_not_required=True)
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
    documents_str = fields.Function(
        fields.Char('Documents'),
        'on_change_with_documents_str')

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls._buttons.update({'generic_send_letter': {}})
        cls._error_messages.update({
                'document_request_for': 'Document Request For',
                })

    def get_request_date(self):
        return utils.today()

    @fields.depends('needed_by')
    def on_change_with_request_description(self, name=None):
        if self.needed_by:
            return '%s %s' % (self.raise_user_error('document_request_for',
                    raise_exception=False), self.needed_by.get_rec_name(name))
        return ''

    def get_contact(self, name=None):
        return self.needed_by.get_main_contact() if self.needed_by else None

    @fields.depends('documents')
    def on_change_with_documents_str(self, name=None):
        return ', '.join([d.document_desc.name for d in self.documents])

    @fields.depends('needed_by')
    def on_change_with_needed_by_str(self, name=None):
        return utils.convert_to_reference(self.needed_by) if \
            self.needed_by else None

    @fields.depends('documents')
    def on_change_with_is_complete(self, name=None):
        return all([x.received for x in self.documents])

    @fields.depends('documents', 'is_complete')
    def on_change_documents(self):
        self.is_complete = self.on_change_with_is_complete()

    @fields.depends('documents', 'is_complete')
    def on_change_is_complete(self):
        if not (self.is_complete or self.documents):
            return
        for document in self.documents:
            document.received = True
            if not document.reception_date:
                document.reception_date = utils.today()
        self.documents = self.documents

    def get_current_docs(self):
        res = {}
        for elem in self.documents:
            res[(elem.document_desc.id, utils.convert_to_reference(
                        elem.for_object))] = elem
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
            if k not in id_docs:
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
        res = super(DocumentRequest, self).get_doc_template_kind()
        res.append('doc_request')
        return res

    def get_object_for_contact(self):
        return self.needed_by

    def get_rec_name(self, name):
        return self.needed_by.get_rec_name(name)

    def get_product(self):
        return self.needed_by.get_product()


class RemindableInterface(object):
    "Remindable Interface"

    __name__ = 'remindable.interface'

    @classmethod
    def get_calculated_required_documents(cls, objects):
        raise NotImplementedError

    @classmethod
    def get_reminder_candidates_query(cls, tables):
        raise NotImplementedError

    def fill_to_remind(cls, doc_per_objects, t_remind, objects,
            force_remind, remind_if_false, treatment_date):
        raise NotImplementedError

    @classmethod
    def get_reminder_group_by_clause(cls, tables):
        raise NotImplementedError

    @classmethod
    def get_reminder_where_clause(cls, tables):
        raise NotImplementedError

    @classmethod
    def get_reminder_candidates_tables(cls):
        tables = {}
        tables[cls.__name__] = cls.__table__()
        tables['document.request.line'] = Pool().get(
            'document.request.line').__table__()
        return tables

    @classmethod
    def get_reminder_candidates(cls):
        cursor = Transaction().connection.cursor()
        tables = cls.get_reminder_candidates_tables()
        query_table = cls.get_reminder_candidates_query(tables)
        having_clause = cls.get_reminder_having_clause(tables)
        group_by_clause = cls.get_reminder_group_by_clause(tables)
        where_clause = cls.get_reminder_where_clause(tables)
        # retrieve all quote contracts which have at least one
        # document_request_line
        cursor.execute(
            *query_table.select(tables[cls.__name__].id,
                where=where_clause,
                group_by=group_by_clause,
                having=having_clause))
        return cursor.fetchall()

    @classmethod
    def get_reminder_having_clause(cls, tables):
        document_request_line = tables['document.request.line']
        return ((Count(document_request_line.id) > 0) &
                (Sum(Case((document_request_line.reception_date == Null, 1),
                            else_=0)) > 0))

    @classmethod
    def generate_reminds_documents(cls, objects, treatment_date=None):
        treatment_date = treatment_date or utils.today()
        force_remind = Transaction().context.get('force_remind', True)
        DocRequestLine = Pool().get('document.request.line')
        to_remind_per_objects = cls.get_document_lines_to_remind(
            objects, force_remind, treatment_date)
        DocRequestLine.update_and_notify_reminders(
            to_remind_per_objects, force_remind, 'remind_documents',
            treatment_date)

    @classmethod
    def get_document_lines_to_remind(cls, objects, force_remind,
            treatment_date=None):
        treatment_date = treatment_date or utils.today()
        DocRequestLine = Pool().get('document.request.line')
        remind_if_false = DocRequestLine.get_default_remind_fields()
        to_remind = defaultdict(list)
        documents_per_object = cls.get_calculated_required_documents(objects)
        cls.fill_to_remind(documents_per_object, to_remind, objects,
            force_remind, remind_if_false, treatment_date)
        return to_remind

    @classmethod
    def is_document_needed(cls, config, documents, doc,
            remind_if_false, force_remind, treatment_date):
        if not config:
            return False
        delay = config.reminder_delay
        unit = config.reminder_unit
        if remind_if_false and all([getattr(doc, x, False)
                for x in remind_if_false]):
            return False
        if not delay or not unit:
            if not force_remind:
                return False
            else:
                return True
        delta = (relativedelta(days=+delay) if unit == 'day'
            else relativedelta(months=+delay))
        if doc.document_desc.code not in documents.keys():
            return False
        doc_max_reminders = documents[
            doc.document_desc.code]['max_reminders']
        if not force_remind and (treatment_date - delta <
                doc.last_reminder_date or
                (doc_max_reminders and
                    doc.reminders_sent >= doc_max_reminders)):
            return False
        return True


class DocumentReception:
    __metaclass__ = PoolMeta
    __name__ = 'document.reception'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        states={'readonly': Eval('state', '') == 'done'}, depends=['state'])
    request = fields.Many2One('document.request.line',
        'Document Request', ondelete='SET NULL',
        domain=[('for_object.id', '=', Eval('party'), 'party.party'),
            ('reception_date', '=', None), ('attachment', '=', None),
            ('document_desc', '=', Eval('document_desc'))],
        states={'readonly': Eval('state', '') == 'done'},
        depends=['document_desc', 'party', 'state'])


class ReceiveDocument:
    __metaclass__ = PoolMeta
    __name__ = 'document.receive'

    def transition_decide(self):
        state = super(ReceiveDocument, self).transition_decide()
        if state != 'free_attach' or not self.free_attach.document:
            return state
        if self.free_attach.document.request:
            self.free_attach.target = self.free_attach.document.request
            return state
        pool = Pool()
        RequestLine = pool.get('document.request.line')
        possible_objects = self.get_possible_objects_from_document(
            self.free_attach.document)
        if possible_objects:
            possible_lines = RequestLine.search([
                    ('reception_date', '=', None),
                    ('attachment', '=', None),
                    ['OR'] + [self.get_object_filtering_clause(x)
                        for x in possible_objects],
                    ('document_desc', '=',
                        self.free_attach.document.document_desc.id),
                    ])
            per_object = {x: [] for x in possible_objects}
            for line in possible_lines:
                self.set_object_line(line, per_object)
            final_lines = []
            matching_sub_line = None
            for record, lines in per_object.items():
                final_lines.append(self.new_line(record))
                for sub_line in lines:
                    final_lines.append(self.new_line(sub_line))
                    final_lines[-1].name = '    ' + final_lines[-1].name
                    if matching_sub_line is None:
                        matching_sub_line = final_lines[-1]
                        final_lines[-1].selected = True
                        final_lines[-1].was_selected = True
            if matching_sub_line:
                self.free_attach.target = matching_sub_line.reference
            elif final_lines:
                self.free_attach.target = final_lines[0].reference
                final_lines[0].selected = True
                final_lines[0].was_selected = True
            self.free_attach.lines = final_lines
        return state

    def get_possible_objects_from_document(self, document):
        return [document.party] if document.party else []

    def get_object_filtering_clause(self, record):
        return [('for_object', '=', str(record))]

    def set_object_line(self, line, per_object):
        per_object[line.for_object].append(line)

    def new_line(self, elem):
        pool = Pool()
        Model = pool.get('ir.model')
        line = pool.get('document.receive.line')()
        line.name = elem.rec_name
        line.reference = elem
        line.selected = False
        line.was_selected = False
        line.type_ = Model(Model.model_id_per_name(elem.__name__)).name
        return line

    def transition_reattach(self):
        request = None
        if self.free_attach.target.__name__ == 'document.request.line':
            request = self.free_attach.target
            self.free_attach.target = request.for_object
        state = super(ReceiveDocument, self).transition_reattach()
        if request is None:
            return state
        request.attachment = self.free_attach.document.attachment
        request.reception_date = self.free_attach.document.reception_date
        request.save()
        return state


class ReattachDocument:
    __metaclass__ = PoolMeta
    __name__ = 'document.receive.reattach'

    lines = fields.One2Many('document.receive.line', None, 'Lines',
        states={'invisible': ~Eval('lines')})

    @classmethod
    def __setup__(cls):
        super(ReattachDocument, cls).__setup__()
        cls.target.states = {'invisible': Bool(Eval('lines'))}

    @fields.depends('lines', 'target')
    def on_change_lines(self):
        selected = None
        for line in self.lines:
            if line.selected and not line.was_selected:
                selected = line
        for line in self.lines:
            if selected:
                line.was_selected = line == selected
                line.selected = line == selected
            else:
                line.was_selected = line.selected
        self.lines = [x for x in self.lines if x.reference]
        if selected:
            self.target = selected.reference
            self.on_change_target()


class ReceiveDocumentLine(model.CoogView):
    'Receive Document Line'

    __name__ = 'document.receive.line'

    name = fields.Char('Name', readonly=True)
    type_ = fields.Char('Type', readonly=True)
    reference = fields.Reference('Reference', 'get_models', readonly=True)
    selected = fields.Boolean('Selected')
    was_selected = fields.Boolean('Was Selected')

    @classmethod
    def get_models(self):
        return utils.models_get()


class DocumentRuleMixin(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    '''
        Mixin class to create document rules.
    '''
    reminder_delay = fields.Integer('Reminder Delay')
    reminder_unit = fields.Selection([
            ('', ''),
            ('month', 'Months'),
            ('day', 'Days')],
        'Reminder Unit', states={'required': Bool(Eval('reminder_delay'))},
        depends=['reminder_delay'])

    @classmethod
    def __setup__(cls):
        super(DocumentRuleMixin, cls).__setup__()
        cls.rule.domain = [('type_', '=', 'doc_request')]
        cls.rule.help = ('The rule must return a dictionnary '
            'with document description codes as keys, and dictionnaries as '
            'values.')

    @staticmethod
    def default_reminder_unit():
        return ''

    def calculate_required_documents(self, data_dict):
        if not self.rule:
            return {}
        rule_result = self.calculate_rule(data_dict)
        if type(rule_result) is not dict:
            self.raise_user_error('wrong_documents_rule')
        return rule_result

    @classmethod
    def merge_results(cls, *args):
        final_result = {}
        for data in args:
            for code, values in data.iteritems():
                if code not in final_result:
                    final_result[code] = values
                    continue
                cls.merge_lines(final_result[code], values)
        return final_result

    @classmethod
    def merge_lines(cls, final, to_merge):
        for k, v in to_merge.iteritems():
            if k not in final:
                final[k] = v
                continue
            if final[k] == v:
                continue
            if k == 'blocking':
                final[k] = v or final[k]
            elif k == 'max_reminders':
                if v and final[k]:
                    final[k] = min(v, final[k])
                elif v:
                    final[k] = v
