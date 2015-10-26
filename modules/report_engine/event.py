from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    'EventTypeActionReportTemplate',
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
    def _export_light(cls):
        return super(EventTypeAction, cls)._export_light() | {
            'report_templates'}

    def execute(self, objects):
        if self.action != 'generate_documents':
            return super(EventTypeAction, self).execute(objects)
        objects_origins_templates = \
            self.get_objects_origins_templates_for_event(objects)
        for objects_, origin, template in objects_origins_templates:
            template.produce_reports(objects_, origin=origin)

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
