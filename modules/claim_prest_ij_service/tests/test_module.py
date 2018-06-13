# encoding: utf8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import random
import string
from lxml.etree import XMLSyntaxError

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.modules.claim_prest_ij_service import gesti_templates


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'claim_prest_ij_service'

    def test0001_test_gesti_templates(self):
        import datetime
        n = datetime.datetime.utcnow()
        n = n.strftime('%Y-%m-%dT%H:%M:%SZ')

        class Party(object):
            @property
            def name(self):
                return u'é hé'

        class Sub(object):
            @property
            def siren(self):
                return ''.join(random.choice(string.digits) for x in range(9))

            @property
            def parties(self):
                return [Party()]

        class Req(object):
            operation = 'cre'

            @property
            def subscription(self):
                return Sub()

        data = dict(
            timestamp=n,
            siret_opedi='example',
            header_id='some id',
            doc_id='some other id',
            gesti_document_filename='example file name',
            gesti_header_identification='example file name',
            gesti_document_identification='example file name',
            access_key='GET FROM CONF',
            identification='an id again',
            code_ga='XXXXX',
            opedi_name='example opedi name',
            requests=[Req() for x in range(5)],
        )
        str(gesti_templates.GestipHeader(data))
        str(gesti_templates.GestipDocument(data))

        data['timestamp'] = 'very invalid timestamp'

        self.assertRaises(XMLSyntaxError,
            gesti_templates.GestipHeader, data)
        self.assertRaises(XMLSyntaxError,
            gesti_templates.GestipDocument, data)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
