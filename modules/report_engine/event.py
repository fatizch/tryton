from itertools import groupby

from trytond.cache import Cache
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields, model
from trytond.wizard import StateView, Button

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    'EventTypeActionReportTemplate',
    'ReportProductionRequest',
    'ConfirmReportProductionRequestTreat',
    'ReportProductionRequestTreatResult',
    'TreatReportProductionRequest',
    ]


class EventTypeActionReportTemplate(model.CoopSQL, model.CoopView):
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
    def get_action_types(cls):
        return super(EventTypeAction, cls).get_action_types() + [
            ('generate_documents', 'Generate Documents')]

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

    def execute(self, objects):
        pool = Pool()
        ReportProductionRequest = pool.get('report_production.request')
        if self.action != 'generate_documents':
            return super(EventTypeAction, self).execute(objects)
        if self.treatment_kind == 'synchronous':
            objects_origins_templates = \
                self.get_objects_origins_templates_for_event(objects)
            for objects_, origin, template in objects_origins_templates:
                template.produce_reports(objects_, origin=origin)
        else:
            ReportProductionRequest.create_report_production_requests(
                self.report_templates, objects)

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

    def template_matches(self, event_object, filtering_objects,
            template):
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

    def get_objects_origins_templates_for_event(self, objects):
        obj_orig_templates = []
        for template, objs in \
                self.get_templates_and_objs_for_event_type(
                    objects).iteritems():
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


class ReportProductionRequest(model.CoopSQL, model.CoopView):
    'Report Production Request'

    __name__ = 'report_production.request'

    report_template = fields.Many2One('report.template', 'Report Template',
        readonly=True)
    object_ = fields.Reference('Object To Report',
        'get_all_printable_models', readonly=True, select=True)
    treated = fields.Boolean('Treated', readonly=True, select=True)

    _get_all_printable_models_cache = Cache('get_all_printable_models')

    @classmethod
    def __setup__(cls):
        super(ReportProductionRequest, cls).__setup__()
        cls._order.insert(0, ('create_date', 'DESC'))

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
    def create_report_production_requests(cls, report_templates, objects):
        cls.create([{'report_template': template, 'object_': str(x)}
                for template in report_templates for x in objects])

    @classmethod
    def treat_requests(cls, report_production_requests):
        all_reports, all_attachments = [], []
        keyfunc = lambda x: x.report_template
        sorted_requests = sorted(list(report_production_requests), key=keyfunc)

        for template, requests in groupby(sorted_requests, key=keyfunc):
            reports, attachments = template.produce_reports([
                    x.object_ for x in requests])
            all_reports.extend(reports)
            all_attachments.extend(attachments)
        cls.write(sorted_requests, {'treated': True})
        return all_reports, all_attachments


class ConfirmReportProductionRequestTreat(model.CoopView):
    'Confirm Report Request Production Treatment'
    __name__ = 'report_production.request.treat.confirm'

    requests = fields.One2Many('report_production.request', None,
        'Report Production Requests', readonly=True)


class ReportProductionRequestTreatResult(model.CoopView):
    'Report Request Production Treatment Result'
    __name__ = 'report_production.request.treat.result'

    attachments = fields.One2Many('ir.attachment', None,
        'Attachments', readonly=True)


class TreatReportProductionRequest(model.CoopWizard):
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
