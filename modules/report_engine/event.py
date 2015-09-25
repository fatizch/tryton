from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'Event',
    'EventType',
    'EventTypeReportTemplate',
    ]


class Event:
    __name__ = 'event'

    @classmethod
    def get_targets_and_origin_from_object_and_template(cls, object_,
            template):
        if template.on_model and template.on_model.model == object_.__name__:
            return [object_], None
        return [], None

    @classmethod
    def get_report_origin(cls, object_, template):
        if template.on_model and template.on_model.model == object_.__name__:
            return None
        else:
            return object_

    @classmethod
    def template_matches(cls, event_object, filtering_objects,
            template):
        return all([template in cls.get_templates_list(filtering_object)
                for filtering_object in filtering_objects])

    @classmethod
    def get_templates_list(cls, filtering_object):
        '''To allow filtering of report templates by event, this method
        should be overloaded to return the list of report_templates associated
        with a filtering_object.'''
        return []

    @classmethod
    def get_filtering_objects_from_event_object(cls, event_object):
        '''This method should be overloaded to return the objects, associated
        with the event_object, that can be linked to a list of report
        templates.

        For example, if A is the event_object, and we have :
            A - m2o -> B - o2m -> report_templates
        this method should return [B]'''
        return []

    @classmethod
    def get_templates_and_objs_for_event_type(cls, event_type, event_objects):
        return {template: cls.filter_objects_for_report(event_objects,
                template) for template in event_type.report_templates}

    @classmethod
    def filter_objects_for_report(cls, event_objects, template):
        res = []
        for event_object in event_objects:
            filtering_objects = cls.get_filtering_objects_from_event_object(
                event_object)
            if filtering_objects:
                if cls.template_matches(event_object, filtering_objects,
                        template):
                    res.append(event_object)
            else:
                res.append(event_object)
        return res

    @classmethod
    def get_objects_origins_templates_for_event(cls, objects, event_type):
        obj_orig_templates = []
        for template, objs in \
                cls.get_templates_and_objs_for_event_type(event_type,
                    objects).iteritems():
            for obj in objs:
                to_print, origin = \
                    cls.get_targets_and_origin_from_object_and_template(
                        obj, template)
                if to_print:
                    obj_orig_templates.append((to_print, origin, template))
        return obj_orig_templates

    @classmethod
    def notify_events(cls, objects, event_code, description=None, **kwargs):
        pool = Pool()
        EventType = pool.get('event.type')
        super(Event, cls).notify_events(objects, event_code, description,
            **kwargs)
        event_type, = EventType.search([('code', '=', event_code)])
        objects_origins_templates = \
            cls.get_objects_origins_templates_for_event(objects, event_type)
        for objects_, origin, template in objects_origins_templates:
            template.produce_reports(objects_, origin=origin)


class EventType:
    __name__ = 'event.type'

    report_templates = fields.Many2Many('event.type-report.template',
            'event_type', 'report_template', 'Report Templates')

    @classmethod
    def _export_light(cls):
        return super(EventType, cls)._export_light() | {'report_templates'}


class EventTypeReportTemplate(model.CoopSQL, model.CoopView):
    'Event Type Report Template Relation'
    __name__ = 'event.type-report.template'

    event_type = fields.Many2One('event.type', 'Event Type',
            ondelete='RESTRICT', required=True, select=True)
    report_template = fields.Many2One('report.template', 'Report Template',
            ondelete='RESTRICT', required=True, select=True)
