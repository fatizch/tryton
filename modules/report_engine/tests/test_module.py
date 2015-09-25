import unittest
from mock import Mock

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework
from trytond.modules.report_engine import event


class ModuleTestCase(test_framework.CoopTestCase):

    module = 'report_engine'

    def test0001_report_event_without_filter(self):
        good_template = Mock()
        good_template.on_model.model = 'good_model'
        bad_template = Mock()
        bad_template.on_model.model = 'bad_model'
        event_type = Mock()
        event_type.report_templates = [good_template, bad_template]
        event_objs = [Mock(__name__='good_model') for x in range(3)]

        result = event.Event.filter_objects_for_report(event_objs,
            good_template)
        self.assertEqual(result, event_objs)

        result = event.Event.get_templates_and_objs_for_event_type(event_type,
                event_objs)
        self.assertEqual(result, {good_template: event_objs,
                bad_template: event_objs})

        result = event.Event.get_objects_origins_templates_for_event(
            event_objs, event_type)
        self.assertEqual(result, [([x], None, good_template) for x in
                event_objs])

    def test_0002_report_event_with_filter(self):

        class MockedEvent(Mock, event.Event):
            @classmethod
            def get_filtering_objects_from_event_object(cls, event_obj):
                return [event_obj.root]

            @classmethod
            def get_templates_list(cls, filter_):
                return filter_.report_templates

        good_template = Mock()
        good_template.on_model.model = 'good_model'
        event_type = Mock()
        event_type.report_templates = [good_template]

        root = Mock(report_templates=[good_template])
        root2 = Mock(report_templates=[])

        to_print = [Mock(__name__='good_model', root=root)
                for x in range(2)]
        event_objs = list(to_print)
        event_objs.append(Mock(__name__='good_model', root=root2))

        res = MockedEvent.template_matches(event_objs[0], [root],
            good_template)
        self.assertEqual(res, True)

        res = MockedEvent.filter_objects_for_report(event_objs, good_template)
        self.assertEqual(res, to_print)

        res = MockedEvent.get_templates_and_objs_for_event_type(event_type,
                event_objs)
        self.assertEqual(res, {good_template: to_print})

        res = MockedEvent.get_objects_origins_templates_for_event(event_objs,
                event_type)
        self.assertEqual(res, [([x], None, good_template) for x in to_print])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
