# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import zipfile
import io
import base64
from mock import Mock
from pathlib import Path
import doctest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import doctest_teardown

from trytond.modules.coog_core import test_framework
from trytond.modules.report_engine import event
from trytond.pool import Pool


class ModuleTestCase(test_framework.CoogTestCase):

    module = 'report_engine'

    def test0001_report_event_without_filter(self):
        event.EventTypeAction.report_templates = None
        event.EventTypeAction.filter_on_target_object = False
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
            filter_on_target_object = False

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

    def test0003_create_report_template(self):
        pool = Pool()
        ReportTemplate = pool.get('report.template')
        Version = pool.get('report.template.version')
        DocumentDesc = pool.get('document.description')
        Lang = pool.get('ir.lang')

        language, = Lang.search([('code', '=', 'en')])

        tester = DocumentDesc(name='tester', code='tester')
        tester.save()

        version = Version()
        version.language = language
        version.name = 'test'

        with open(Path(__file__).parent / 'basic_odt_template.fodt', 'rb') as f:
            version.data = f.read()

        report_template = ReportTemplate()
        report_template.name = 'report_template_for_test'
        report_template.code = 'report_template_for_test'
        report_template.on_model = None
        report_template.document_desc = tester
        report_template.input_kind = 'libre_office_odt'
        report_template.format_for_internal_edm = 'original'
        report_template.versions = [version]
        report_template.output_format = 'libre_office'
        report_template.save()

    @test_framework.prepare_test(
        'report_engine.test0003_create_report_template')
    def test0004_generate_documents_api(self):
        pool = Pool()
        APIReport = pool.get('api.report')
        EventTypeAction = pool.get('event.type.action')
        Attachment = pool.get('ir.attachment')
        ReportTemplate = pool.get('report.template')
        test_template, = ReportTemplate.search([
                ('code', '=', 'report_template_for_test')])

        action = EventTypeAction(
            name='test1', code='test1',
            priority=10,
            action='generate_documents')
        action.save()
        action.report_templates += (test_template, )
        action.save()

        filter_id = action.id

        input_data = {
            'records': [
                {
                    'data': {'talk': 'quack'},
                }
            ],
            'documents': [{'code': 'tester'}],
            'filters': [{'model': 'event.type.action', 'id': filter_id}]
        }

        result = APIReport.generate_documents(input_data,
            {'_debug_server': True})
        attachment, = Attachment.search([('resource', '=', str(test_template))])
        document = result['documents'][0]
        self.assertEqual(document['edm_id'], str(attachment.id))
        self.assertEqual(document['metadata']['extension'], 'odt')
        self.assertEqual(document['metadata']['document_desc'],
            {'code': 'tester'})
        self.assertEqual(document['metadata']['template'],
            {'code': 'report_template_for_test'})

        data = io.BytesIO()
        data.write(attachment.data)
        with zipfile.ZipFile(data, mode='r') as z:
            content = z.read('content.xml')
        self.assertTrue(b'quack' in content)

    @test_framework.prepare_test(
        'report_engine.test0004_generate_documents_api')
    def test0005_get_document_api(self):
        pool = Pool()
        APIReport = pool.get('api.report')
        Attachment = pool.get('ir.attachment')
        ReportTemplate = pool.get('report.template')
        test_template, = ReportTemplate.search([
                ('code', '=', 'report_template_for_test')])
        attachment, = Attachment.search([('resource', '=', str(test_template))])

        input_data = {
            'edm_id': str(attachment.id)
        }

        result = APIReport.get_document(input_data,
            {'_debug_server': True})
        data = result['data']
        binary_data = base64.b64decode(data)
        f = io.BytesIO()
        f.write(binary_data)
        with zipfile.ZipFile(f, mode='r') as z:
            content = z.read('content.xml')
        self.assertTrue(b'quack' in content)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_genshi_shared_template.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
