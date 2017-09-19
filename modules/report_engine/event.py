# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json

from itertools import groupby
from collections import defaultdict
import datetime

from trytond.protocols.jsonrpc import JSONEncoder, JSONDecoder
from trytond.cache import Cache
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields, model
from trytond.wizard import StateView, Button

from .report_engine import Printable

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    'EventTypeActionReportTemplate',
    'ReportProductionRequest',
    'ConfirmReportProductionRequestTreat',
    'ReportProductionRequestTreatResult',
    'TreatReportProductionRequest',
    ]


class EventTypeActionReportTemplate(model.CoogSQL, model.CoogView):
    'Event Type Action Template Relation'
    __name__ = 'event.type.action-report.template'

    event_type_action = fields.Many2One('event.type.action',
        'Event Type Action', ondelete='CASCADE', required=True, select=True)
    report_template = fields.Many2One('report.template', 'Report Template',
            ondelete='CASCADE', required=True, select=True)


class EventTypeAction:
    __name__ = 'event.type.action'

    report_templates = fields.Many2Many('event.type.action-report.template',
            'event_type_action', 'report_template', 'Report Templates',
        states={'invisible': Eval('action') != 'generate_documents'})

    @classmethod
    def __setup__(cls):
        super(EventTypeAction, cls).__setup__()
        cls._error_messages.update({'generate_documents': 'Generate Documents'})

    @classmethod
    def get_action_types(cls):
        return super(EventTypeAction, cls).get_action_types() + [
            ('generate_documents', cls.raise_user_error(
                    'generate_documents', raise_exception=False))]

    @classmethod
    def default_treatment_kind(cls):
        return 'synchronous'

    @fields.depends('report_templates')
    def on_change_action(self):
        super(EventTypeAction, self).on_change_action()
        self.report_templates = []
        self.treatment_kind = 'synchronous'

    @classmethod
    def possible_asynchronous_actions(cls):
        return super(EventTypeAction, cls).possible_asynchronous_actions() + \
            ['generate_documents']

    @classmethod
    def _export_light(cls):
        return super(EventTypeAction, cls)._export_light() | {
            'report_templates'}

    def action_generate_documents(self, objects, event_code, description,
            **kwargs):
        pool = Pool()
        ReportProductionRequest = pool.get('report_production.request')
        objects_origins_templates = \
            self.get_objects_origins_templates_for_event(objects)
        ProductionRequestBatch = pool.get(
            'report_production.request.batch_treat')
        requests_per_template = defaultdict(list)

        for objects_to_report, origin, template in objects_origins_templates:
            context_ = self.build_context(objects_to_report, origin,
                event_code)
            if self.treatment_kind == 'synchronous':
                template.produce_reports(objects_to_report, context_)
            elif self.treatment_kind == 'asynchronous':
                ReportProductionRequest.create_report_production_requests(
                    template, objects_to_report, context_)
            elif self.treatment_kind == 'asynchronous_queue':
                requests = \
                    ReportProductionRequest.create_report_production_requests(
                        template, objects_to_report, context_)
                requests_per_template[template.id].extend(requests)
        for template, requests in requests_per_template.items():
            if not requests:
                continue
            ProductionRequestBatch.enqueue([(x.id,) for x in requests], {},
                user=Transaction().user)

    def execute(self, objects, event_code, description=None, **kwargs):
        if self.action != 'generate_documents':
            return super(EventTypeAction, self).execute(objects, event_code)
        self.action_generate_documents(objects, event_code, description,
            **kwargs)

    def build_context(self, objects_to_report, origin, event_code):
        context_ = {'event_code': event_code}
        if origin:
            context_.update({'origin': origin})
        if origin and isinstance(origin, Printable):
            functional_date = origin.get_report_functional_date(event_code)
        else:
            functional_date = objects_to_report[0].get_report_functional_date(
                event_code)
        if functional_date:
            context_.update({'functional_date': functional_date})
        return context_

    def get_targets_and_origin_from_object_and_template(self, object_,
            template):
        if template.on_model and template.on_model.model == object_.__name__:
            return [object_], None
        return [], None

    @classmethod
    def get_report_origin(self, object_, template):
        if template.on_model and template.on_model.model == object_.__name__:
            return None
        else:
            return object_

    def template_matches(self, event_object, filtering_objects, template):
        return all([template in self.get_templates_list(filtering_object)
                for filtering_object in filtering_objects])

    def get_templates_list(self, filtering_object):
        '''To allow filtering of report templates by event, this method
        should be overloaded to return the list of report_templates associated
        with a filtering_object.'''
        return []

    def get_filtering_objects_from_event_object(self, event_object):
        '''This method should be overloaded to return the objects, associated
        with the event_object, that can be linked to a list of report
        templates.

        For example, if A is the event_object, and we have :
            A - m2o -> B - o2m -> report_templates
        this method should return [B]'''
        return []

    def get_templates_and_objs_for_event_type(self, event_objects):
        return {template: self.filter_objects_for_report(event_objects,
                template) for template in self.report_templates}

    def filter_objects_for_report(self, event_objects, template):
        res = []
        for event_object in event_objects:
            filtering_objects = self.get_filtering_objects_from_event_object(
                event_object)
            if filtering_objects:
                if self.template_matches(event_object, filtering_objects,
                        template):
                    res.append(event_object)
            else:
                res.append(event_object)
        return res

    def get_objects_origins_templates_for_event(self, event_objects):
        obj_orig_templates = []
        for template, objs in \
                self.get_templates_and_objs_for_event_type(
                    event_objects).iteritems():
            for obj in objs:
                to_print, origin = \
                    self.get_targets_and_origin_from_object_and_template(
                        obj, template)
                if to_print:
                    obj_orig_templates.append((to_print, origin, template))
        return obj_orig_templates

    def cache_data(self):
        data = super(EventTypeAction, self).cache_data()
        data['report_templates'] = [x.id for x in self.report_templates]
        return data


class ReportProductionRequest(model.CoogSQL, model.CoogView):
    'Report Production Request'

    _func_key = 'id'
    __name__ = 'report_production.request'

    report_template = fields.Many2One('report.template', 'Report Template',
        readonly=True, ondelete='RESTRICT')
    object_ = fields.Reference('Object To Report',
        'get_all_printable_models', readonly=True, select=True)
    treated = fields.Boolean('Treated', readonly=True, select=True)
    context_ = fields.Char('Reporting Context')
    _get_all_printable_models_cache = Cache('get_all_printable_models')

    @classmethod
    def __setup__(cls):
        super(ReportProductionRequest, cls).__setup__()
        cls._order.insert(0, ('create_date', 'DESC'))

    @classmethod
    def _export_light(cls):
        return (super(ReportProductionRequest, cls)._export_light() |
            {'object_', 'report_template'})

    @classmethod
    def default_treated(cls):
        return False

    @classmethod
    def get_all_printable_models(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        res = cls._get_all_printable_models_cache.get('models', None)
        if not res:
            res = [(x.model, x.name) for x in Model.search(
                    [('printable', '=', True)])]
            cls._get_all_printable_models_cache.set('models', res)
        return res

    @classmethod
    def create_report_production_requests(cls, report_template, objects,
            context_):
        cls.make_json_serializable(context_)
        return cls.create([{'report_template': report_template,
                    'object_': str(x),
                    'context_': json.dumps(context_, cls=JSONEncoder)}
                for x in objects])

    @classmethod
    def treat_requests(cls, report_production_requests):
        all_reports, all_attachments = [], []

        def group_prod_requests(x):
            return x.report_template
        report_production_requests = sorted(report_production_requests,
            key=group_prod_requests)
        for template, values in groupby(report_production_requests,
                group_prod_requests):
            values = list(values)

            def genexp_sort(x):
                if not template.split_reports:
                    return x.context_
                else:
                    return x.id

            values = sorted(values, key=genexp_sort)
            for _, requests in groupby(values, genexp_sort):
                requests = list(requests)
                to_treat = [x.object_ for x in requests]
                context_ = json.loads(requests[0].context_,
                    object_hook=JSONDecoder())
                cls.instantiate_from_dict(context_)
                reports, attachments = requests[0].\
                    report_template.produce_reports(to_treat, context_)
                all_reports.extend(reports)
                all_attachments.extend(attachments)
        cls.write(list(report_production_requests), {'treated': True})
        return all_reports, all_attachments

    @classmethod
    def make_json_serializable(cls, to_jsonize):
        for name in ('origin', 'resource'):
            if name in to_jsonize and to_jsonize[name]:
                to_jsonize[name] = str(to_jsonize[name])

    @classmethod
    def instantiate_from_dict(cls, values):
        pool = Pool()
        for name in ('origin', 'resource'):
            if name in values:
                model_name, id_ = values[name].split(',')
                values[name] = pool.get(model_name)(id_)

    def get_rec_name(self, name):
        try:
            start = json.loads(self.context_)['validity_start']
            end = json.loads(self.context_)['validity_end']
            start_date = datetime.date(
                start['year'], start['month'], start['day'])
            end_date = datetime.date(
                end['year'], end['month'], end['day'])
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            return '%s/%s' % (start_str, end_str)
        except KeyError:
            return ''


class ConfirmReportProductionRequestTreat(model.CoogView):
    'Confirm Report Request Production Treatment'
    __name__ = 'report_production.request.treat.confirm'

    requests = fields.One2Many('report_production.request', None,
        'Report Production Requests', readonly=True)


class ReportProductionRequestTreatResult(model.CoogView):
    'Report Request Production Treatment Result'
    __name__ = 'report_production.request.treat.result'

    attachments = fields.One2Many('ir.attachment', None,
        'Attachments', readonly=True)


class TreatReportProductionRequest(model.CoogWizard):
    'Treat Report Production Request'

    __name__ = 'report_production.request.treat'

    start_state = 'confirm_production'
    confirm_production = StateView('report_production.request.treat.confirm',
        'report_engine.confirm_report_production_request_treatment_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('Confirm', 'result', 'tryton-go-next', default=True)])
    result = StateView('report_production.request.treat.result',
        'report_engine.report_production_request_treatment_result_view_form',
        [Button('Ok', 'end', 'tryton-ok', default=True)])

    def default_confirm_production(self, name):
        context_ = Transaction().context
        assert context_.get('active_model', None) == \
            'report_production.request'
        return {'requests': context_.get('active_ids', [])}

    def default_result(self, name):
        pool = Pool()
        ReportProductionRequest = pool.get('report_production.request')
        _, attachments = ReportProductionRequest.treat_requests(
            self.confirm_production.requests)
        return {'attachments': [x.id for x in attachments]}