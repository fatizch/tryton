# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import mock

import trytond.tests.test_tryton
from trytond.exceptions import UserError

from trytond.modules.coog_core import test_framework, utils


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'document_request'

    @classmethod
    def get_models(cls):
        return {
            'DocumentRequestLine': 'document.request.line',
            'DocumentDescription': 'document.description',
            'Attachment': 'ir.attachment',
            'ExportTest': 'coog_core.export_test',
            }

    def create_doc_request_line(self, code="doc"):
        test_object = self.ExportTest()
        test_object.save()
        doc_desc = self.DocumentDescription(name="Doc", code=code)
        doc_desc.save()
        self.DocumentRequestLine.for_object_models = mock.MagicMock(
            return_value=['coog_core.export_test'])
        line = self.DocumentRequestLine(document_desc=doc_desc,
            for_object=test_object)
        line.save()
        return line, doc_desc, test_object

    def test01_create_doc_request_line(self):
        line, _, _ = self.create_doc_request_line()
        self.assertFalse(line.received)
        self.assertEqual(line.reception_date, None)
        self.assertEqual(line.first_reception_date, None)

    def test02_on_change_attachment(self):
        line, doc_desc, test_object = self.create_doc_request_line()
        attachment = self.Attachment(resource=test_object,
            document_desc=doc_desc, name='test', data='')
        attachment.save()
        line.attachment = attachment
        line.on_change_attachment()
        # on_change_with_received will be also called by the client
        line.received = line.on_change_with_received()
        self.assertTrue(line.received)
        self.assertEqual(line.reception_date, utils.today())
        self.assertEqual(line.first_reception_date, utils.today())
        line.attachment.status = 'invalid'
        line.attachment.is_conform = \
            line.attachment.on_change_with_is_conform('')
        line.on_change_attachment()
        self.assertTrue(line.received)
        self.assertEqual(line.reception_date, utils.today())
        self.assertEqual(line.first_reception_date, utils.today())

    def test03_attachment_domain(self):
        line, doc_desc, test_object = self.create_doc_request_line()

        bad_desc = self.DocumentDescription(name="Doc", code='booh')
        bad_desc.save()
        attachment_bad_desc = self.Attachment(resource=test_object,
            document_desc=bad_desc, name='test', data='')
        attachment_bad_desc.save()
        line.attachment = attachment_bad_desc
        self.assertRaises(UserError, line.save)

        bad_object = self.ExportTest()
        bad_object.save()

        attachment_bad_object = self.Attachment(resource=bad_object,
            document_desc=doc_desc, name='test', data='')
        attachment_bad_object.save()
        line.attachment = attachment_bad_object
        self.assertRaises(UserError, line.save)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite
