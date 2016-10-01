# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from mock import Mock

import trytond.tests.test_tryton

from trytond.modules.coog_core import test_framework
from trytond.modules.report_engine import event


class ModuleTestCase(test_framework.CoogTestCase):

    module = 'report_engine'

    def test0001_report_event_without_filter(self):
        event.EventTypeAction.report_templates = None
        good_template = Mock()
        good_template.on_model.model = 'good_model'
        bad_template = Mock()
        bad_template.on_model.model = 'bad_model'
        action = event.EventTypeAction()
        action.report_templates = [good_template, bad_template]
        event_objs = [Mock(__name__='good_model') for x in range(3)]

        result = action.filter_objects_for_report(event_objs,
            good_template)
        self.assertEqual(result, event_objs)

        result = action.get_templates_and_objs_for_event_type(event_objs)
        self.assertEqual(result, {good_template: event_objs,
                bad_template: event_objs})

        result = action.get_objects_origins_templates_for_event(event_objs)
        self.assertEqual(result, [([x], None, good_template) for x in
                event_objs])

    def test_0002_report_event_with_filter(self):

        class MockedEventTypeAction(Mock, event.EventTypeAction):
            report_templates = None

            def get_filtering_objects_from_event_object(self, event_obj):
                return [event_obj.root]

            def get_templates_list(self, filter_):
                return filter_.report_templates

        good_template = Mock()
        good_template.on_model.model = 'good_model'
        action = MockedEventTypeAction()
        action.report_templates = [good_template]

        root = Mock(report_templates=[good_template])
        root2 = Mock(report_templates=[])

        to_print = [Mock(__name__='good_model', root=root)
                for x in range(2)]
        event_objs = list(to_print)
        event_objs.append(Mock(__name__='good_model', root=root2))

        res = action.template_matches(event_objs[0], [root],
            good_template)
        self.assertEqual(res, True)

        res = action.filter_objects_for_report(event_objs, good_template)
        self.assertEqual(res, to_print)

        res = action.get_templates_and_objs_for_event_type(event_objs)
        self.assertEqual(res, {good_template: to_print})

        res = action.get_objects_origins_templates_for_event(event_objs)
        self.assertEqual(res, [([x], None, good_template) for x in to_print])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
