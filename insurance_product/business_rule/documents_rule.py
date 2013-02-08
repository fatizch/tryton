#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pool import Pool
from trytond.wizard import Wizard, StateAction
from trytond.report import Report

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
]


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
            'readonly': True
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
            if (hasattr(self, 'reception_date') and self.reception_date):
                return {'reception_date': None}
            else:
                return {'reception_date': utils.today()}

    def on_change_with_reception_date(self, name=None):
        if (hasattr(self, 'attachment') and self.attachment):
            if (hasattr(self, 'reception_date') and self.reception_date):
                return self.reception_date
            else:
                return utils.today()

    def get_rec_name(self, name):
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


class DocumentRequest(model.CoopSQL, model.CoopView):
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


class GenerateGraph(Report):
    __name__ = 'process.graph_generation'

    @classmethod
    def execute(cls, ids, data):
        ActionReport = Pool().get('ir.action.report')

        action_report_ids = ActionReport.search([
            ('report_name', '=', cls.__name__)
        ])
        if not action_report_ids:
            raise Exception('Error', 'Report (%s) not find!' % cls.__name__)
        action_report = ActionReport(action_report_ids[0])

        Process = Pool().get('process.process_desc')
        the_process = Process(Transaction().context.get('active_id'))

        graph = cls.build_graph(the_process)

        nodes = {}

        for step in the_process.get_all_steps():
            cls.build_step(the_process, step, graph, nodes)

        edges = {}

        for transition in the_process.transitions:
            if transition.kind == 'next':
                cls.build_transition(
                    the_process, step, transition, graph, nodes, edges)

        for transition in the_process.transitions:
            if transition.kind == 'previous':
                cls.build_inverse_transition(
                    the_process, step, transition, graph, nodes, edges)

        for transition in the_process.transitions:
            if transition.kind == 'complete':
                cls.build_complete_transition(
                    the_process, step, transition, graph, nodes, edges)

        nodes[the_process.first_step().id].set('style', 'filled')
        nodes[the_process.first_step().id].set('shape', 'octagon')
        nodes[the_process.first_step().id].set('fillcolor', '#0094d2')

        for node in nodes.itervalues():
            graph.add_node(node)

        for edge in edges.itervalues():
            graph.add_edge(edge)

        data = graph.create(prog='dot', format='pdf')
        return ('pdf', buffer(data), False, action_report.name)


class GenerateGraphWizard(Wizard):
    __name__ = 'process.generate_graph_wizard'

    start_state = 'print_'

    print_ = StateAction('process.report_generate_graph')

    def transition_print_(self):
        return 'end'

    def do_print_(self, action):
        return action, {
            'id': Transaction().context.get('active_id'),
        }
