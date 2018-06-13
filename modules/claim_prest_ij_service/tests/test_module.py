# encoding: utf8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from lxml.etree import XMLSyntaxError

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.modules.claim_prest_ij_service import gesti_templates


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'claim_prest_ij_service'

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'Subscription': 'claim.ij.subscription',
            }

    def test0001_test_gesti_templates(self):
        import datetime
        n = datetime.datetime.utcnow()
        n = n.strftime('%Y-%m-%dT%H:%M:%SZ')

        siren = '379158322'
        ssn = '180104161674907'
        ssn2 = '180106741921625'
        ssn3 = '180104807063318'

        Party = self.Party
        Subscription = self.Subscription

        company = Party(name='Company', siren=siren)
        company.save()
        person = Party(name=u'ééé', first_name='joe', ssn=ssn)
        person.save()
        person = Party(name=u'doe', first_name='jane', ssn=ssn2)
        person.save()
        person = Party(name=u'dane', first_name='jane', ssn=ssn3)
        person.save()

        class Req(object):

            def __init__(self, ssn='', period_end=False, operation='cre'):
                sub_args = {'siren': siren, 'ssn': ssn}
                self.subscription = Subscription(**sub_args)
                self.subscription.save()
                self.period_end = None if not period_end \
                    else datetime.date.today()
                self.period_start = datetime.date.today()
                self.retro_date = datetime.date.today()
                self.period_identification = '001'
                self.operation = operation

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
            requests=[Req(), Req(ssn=ssn, period_end=True),
                Req(ssn=ssn2), Req(ssn=ssn3, operation='sup')]
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
