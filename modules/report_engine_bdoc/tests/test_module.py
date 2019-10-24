# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import requests_mock

import trytond.tests.test_tryton
from trytond.pool import Pool
from trytond.config import config

from trytond.modules.coog_core import test_framework, utils


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'report_engine_bdoc'

    def test_call_api(self):
        pool = Pool()
        Template = pool.get('report.template')
        Lang = pool.get('ir.lang')
        SharedTemplate = pool.get('report.shared_template')
        lang_fr, = Lang.search([('code', '=', 'fr')])
        Party = pool.get('party.party')
        party = Party(name='test bodc', rec_name='test bodc')
        party.save()
        shared_template = SharedTemplate(name='Test Template 1',
            code='test_template_1', data=b'<a>test template 1</a>')
        shared_template.save()
        template_1 = Template()
        template_1.name = 'Test Template 1'
        template_1.code = 'test_template_1'
        template_1.input_kind = 'bdoc'
        template_1.process_method = 'bdoc'
        template_1.BDOC_production_format = 'pdf'
        template_1.BDOC_template_domain = 'Contract'
        template_1.versions = [{
            'language': lang_fr,
            'start_date': utils.today(),
            'shared_template': shared_template,
            'name': 'Test Template 1',
             }]
        template_1.save()
        config.add_section('bdoc')
        test_file_path = utils.get_module_path(
            'report_engine_bdoc') + '/tests/test_files/BdocWebWS.xml'
        config.set('bdoc', 'bdoc_web_wsdl', test_file_path)

        response = '''
        <S:Envelope xmlns:S="http://www.w3.org/2003/05/soap-envelope">
            <S:Body>
                <ns2:generationResponse xmlns:ns2="http://service.bdoc.com/">
                    <return xsi:type="ns2:documentInfo"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                        <id>0</id>
                        <sessionID>?</sessionID>
                        <structContent><![CDATA[<?xml version="1.0"?>
                            <root>
                            <Styles></Styles>
                            <DocumentStruct variantCode=""></DocumentStruct>
                            </root>]]>
                        </structContent>
                        <contentType>application/pdf</contentType>
                        <documents>
                           <document>
                               JVBERi0xLjQKJaqrrK0KNCAwIG9iago8PAovQXV0aG9yICgpCi9
                               TdWJqZWN0ICgpCi9LZXl3b3JkcyAoKQovQ3JlYXRvciAoQmRvY1
                               BERiBWNS4xKQovUHJvZHVjZXIgKEFwYWNoZSBGT1AgVmVyc2lvbi
                               Bzdm4tdHJ1bmspCi9D
                            </document>
                        </documents>
                    </return>
                </ns2:generationResponse>
            </S:Body>
        </S:Envelope>
               '''
        ReportGenerate = Pool().get('report.generate', type='report')
        with requests_mock.mock() as m:
            m.post('http://172.18.2.73:8180/bdocweb-ws-5.1/BdocWebWS',
                text=response)
            return_data = ReportGenerate.process_bdoc([],
                {'doc_template': [template_1.id],
                 'sender': 1,
                 'model': 'party.party',
                 'party': None,
                 'address': None,
                 'sender_address': 1,
                 'id': party.id,
                 'ids': [party.id],
                 'origin': None,
                 'objects': [party],
                 'recipient_email': ''})

        self.assertEqual(return_data[:-1], (
            template_1.BDOC_production_format,
            b'%PDF-1.4\n%\xaa\xab\xac\xad\n4 0 obj\n<<\n/Author ()\n/Subject '
            b'()\n/Keywords ()\n/Creator (BdocPDF V5.1)\n/Producer '
            b'(Apache FOP Version svn-trunk)\n/C',
            False
        ))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
