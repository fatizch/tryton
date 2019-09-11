# encoding: utf8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import mock
from lxml.etree import XMLSyntaxError

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework, coog_date
from trytond.modules.claim_prest_ij_service import gesti_templates
import datetime


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'claim_prest_ij_service'

    @classmethod
    def fetch_models_for(cls):
        return ['offered_insurance', 'contract']

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'Subscription': 'claim.ij.subscription',
            'ItemDesc': 'offered.item.description',
            'CoveredElement': 'contract.covered_element',
            'Claim': 'claim',
            'ClaimClosingReason': 'claim.closing_reason',
            'Service': 'claim.service',
            'Benefit': 'benefit',
            'Loss': 'claim.loss',
            'LossDesc': 'benefit.loss.description',
            'Insurer': 'insurer',
            'Request': 'claim.ij.subscription_request',
            'SubscriptionBatch': 'prest_ij.subscription.create',
            'SubmitPersonPrestIjSubscription':
            'prest_ij.subscription.submit_person',
            'RequestGroup': 'claim.ij.subscription_request.group',
            }

    def run_subscription_batch(self):
        SubscriptionBatch = self.SubscriptionBatch
        treatment_date = datetime.date.today()
        ids = SubscriptionBatch.select_ids(
            treatment_date=treatment_date,
            kind='person')
        SubscriptionBatch.execute(ids, ids, treatment_date,
            kind='person')
        return ids

    def run_submit_person_batch(self, operation='cre'):
        SubmitPerson = \
            self.SubmitPersonPrestIjSubscription
        treatment_date = datetime.date.today()
        ids = SubmitPerson.select_ids(
            treatment_date=treatment_date, operation=operation)
        objects = \
            list(SubmitPerson.convert_to_instances(ids))
        SubmitPerson.execute(objects,
            ids, treatment_date, operation=operation)
        return ids

    def test0001_test_gesti_templates(self):
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
        person = Party(name='ééé', first_name='joe', ssn=ssn)
        person.save()
        person = Party(name='doe', first_name='jane', ssn=ssn2)
        person.save()
        person = Party(name='dane', first_name='jane', ssn=ssn3)
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
        gesti_templates.GestipHeader(data)
        gesti_templates.GestipDocument(data)

        data['timestamp'] = 'very invalid timestamp'

        self.assertRaises(XMLSyntaxError,
            gesti_templates.GestipHeader, data)
        self.assertRaises(XMLSyntaxError,
            gesti_templates.GestipDocument, data)

    @test_framework.prepare_test(
        'offered_insurance.test0010Coverage_creation',
        'contract.test0005_PrepareProductForSubscription',
        )
    def test0002_test_create_ij_subscription_batch(self):
        birth_date = datetime.date(1980, 1, 1)
        person_a = self.Party(name='person_a', first_name='a',
            is_person=True, birth_date=birth_date, gender='male',
            ssn='180107710378929')
        person_a.save()
        person_b = self.Party(name='person_b', first_name='b',
            is_person=True, birth_date=birth_date, gender='male',
            ssn='180105059921334')
        person_b.save()
        siren_a = '552100554'
        big_company_a = self.Party(name='Big A', siren=siren_a)
        big_company_a.save()

        siren_b = '800403222'
        big_company_b = self.Party(name='Big B', siren=siren_b)
        big_company_b.save()

        product, = self.Product.search([
                ('code', '=', 'AAA'),
                ])
        product.start_date = datetime.date(2001, 1, 1)
        product.save()
        start_date = product.start_date + datetime.timedelta(weeks=4)

        category_item_desc = self.ItemDesc()
        category_item_desc.name = 'population'
        category_item_desc.code = 'category_item_desc'
        category_item_desc.kind = None
        category_item_desc.save()

        person_item_desc, = self.ItemDesc.search([('code', '=', 'person')])

        def create_contract(subscriber, person):
            contract = self.Contract(
                product=product.id,
                company=product.company.id,
                start_date=start_date,
                appliable_conditions_date=start_date,
                subscriber=subscriber,
                )
            contract.save()

            population = self.CoveredElement()
            population.contract = contract
            population.name = 'population lambda'
            population.item_desc = category_item_desc
            population.save()

            person_cov = self.CoveredElement()
            person_cov.party = person
            person_cov.contract = contract
            person_cov.parent = population
            person_cov.item_desc = person_item_desc
            person_cov.manual_start_date = start_date
            person_cov.save()

            return contract

        create_contract(big_company_a, person_a)

        subscription_big_a = self.Subscription(siren=siren_a,
            state='declaration_confirmed', activated=True,
            ij_activation=True)
        subscription_big_a.save()
        assert bool(subscription_big_a.activated) is True

        self.run_subscription_batch()

        person_a_sub, = self.Subscription.search([
            ('ssn', '=', person_a.ssn),
            ('siren', '=', siren_a)])

        self.run_subscription_batch()
        person_a_sub, = self.Subscription.search([
            ('ssn', '=', person_a.ssn),
            ('siren', '=', siren_a)])
        all_ = self.Subscription.search([])
        assert len(all_) == 2

        create_contract(big_company_b, person_a)
        subscription_big_b = self.Subscription(siren=siren_b,
            state='declaration_confirmed', activated=True,
            ij_activation=True)
        subscription_big_b.save()
        all_ = self.Subscription.search([])
        assert len(all_) == 3
        assert bool(subscription_big_b.activated) is True
        self.run_subscription_batch()
        person_a_sub_big_b, = self.Subscription.search([
            ('ssn', '=', person_a.ssn),
            ('siren', '=', siren_b)])

        all_ = self.Subscription.search([])
        assert len(all_) == 4
        self.run_subscription_batch()
        all_ = self.Subscription.search([])
        assert len(all_) == 4

        person_a_sub.state = 'declaration_confirmed'
        person_a_sub.save()

    @test_framework.prepare_test(
        'claim_prest_ij_service.test0002_test_create_ij_subscription_batch',
        )
    def test0003_test_create_benefit(self):
        product, = self.Product.search([
                ('code', '=', 'AAA'),
                ])
        contract_big_a, = self.Contract.search([
                ('subscriber.name', '=', 'Big A')])

        invalidity_reason = self.ClaimClosingReason()
        invalidity_reason.code = 'invalidity'
        invalidity_reason.name = 'Passage en invalidité'
        invalidity_reason.save()

        std = self.LossDesc()
        std.code = 'std'
        std.name = 'std'
        std.has_end_date = True
        std.kind = 'person'
        std.loss_kind = 'std'
        std.company = product.company
        std.closing_reasons = [invalidity_reason]
        std.save()

        insurer = self.Insurer.search([])[0]
        benefit = self.Benefit()
        benefit.code = 'std'
        benefit.name = 'std'
        benefit.start_date = product.start_date
        benefit.insurer = insurer
        benefit.company = product.company
        benefit.indemnification_kind = 'capital'
        benefit.loss_descs = [std]
        benefit.prest_ij = True
        benefit.save()

    @test_framework.prepare_test(
        'claim_prest_ij_service.test0003_test_create_benefit',
        )
    def test0004_test_submit_person(self):
        person_a, = self.Party.search([('first_name', '=', 'a')])
        benefit, = self.Benefit.search([])
        std, = self.LossDesc.search([])
        invalidity_reason, = self.ClaimClosingReason.search([])
        contract_big_a, = self.Contract.search([
                ('subscriber.name', '=', 'Big A')])
        Request = self.Request

        claim = self.Claim()
        claim.claimant = person_a
        claim.save()

        def patch(f):
            def decorated(**kwargs):
                RequestGroup = self.RequestGroup
                Service = self.Service
                with mock.patch.object(RequestGroup, 'generate_identification'
                        ) as gen_id_patched, \
                        mock.patch.object(Service, 'deductible_end_date',
                            new_callable=mock.PropertyMock
                            ) as deduc_end_patched:
                    gen_id_patched.return_value = '123'
                    deduc_end_patched.return_value = kwargs.get(
                        'deductible_end_date', None)
                    return f(**kwargs)
            return decorated

        @patch
        def test_loss_case(
                start_date,
                end_date,
                deductible_end_date,
                operation,
                should_create):
            self.run_submit_person_batch(operation='sup')
            requests = Request.search([])
            assert len(requests) == 0
            self.run_submit_person_batch(operation='cre')
            requests = Request.search([])
            assert len(requests) == 0
            loss = self.Loss()
            loss.loss_desc = std
            loss.covered_person = person_a
            loss.claim = claim

            loss.start_date = start_date
            loss.end_date = end_date
            if end_date:
                loss.closing_reason = invalidity_reason
            loss.save()

            service = self.Service()
            service.loss = loss
            service.contract = contract_big_a
            service.benefit = benefit
            service.save()

            def validate():
                requests = Request.search([])
                if should_create:
                    request, = requests
                    assert request.operation == operation
                else:
                    assert len(requests) == 0

            self.run_submit_person_batch(operation=operation)
            validate()
            self.run_submit_person_batch(operation=operation)
            validate()

            self.Loss.delete([loss])
            self.Service.delete([service])
            Request.delete(Request.search([]))

        three_months_ago = coog_date.add_month(datetime.date.today(), -3)
        test_loss_case(
            start_date=None,
            end_date=three_months_ago,
            deductible_end_date=None,
            operation='sup',
            should_create=True)

        person_a_sub, = self.Subscription.search([
            ('ssn', '=', person_a.ssn),
            ('siren', '=', contract_big_a.subscriber.siren)])
        person_a_sub.state = 'undeclared'
        person_a_sub.save()

        yesterday = coog_date.add_day(datetime.date.today(), -1)
        # test_loss_case(
        #     start_date=yesterday,
        #     end_date=datetime.date.today(),
        #     deductible_end_date=None,
        #     operation='cre',
        #     should_create=True)

        # two_days_ago = coog_date.add_day(datetime.date.today(), -2)
        # test_loss_case(
        #     start_date=two_days_ago,
        #     end_date=yesterday,
        #     deductible_end_date=None,
        #     operation='cre',
        #     should_create=True)

        test_loss_case(
            start_date=yesterday,
            end_date=None,
            deductible_end_date=yesterday,
            operation='cre',
            should_create=True)

        tomorrow = coog_date.add_day(datetime.date.today(), 1)
        test_loss_case(
            start_date=yesterday,
            end_date=None,
            deductible_end_date=tomorrow,
            operation='cre',
            should_create=False)

        test_loss_case(
            start_date=yesterday,
            end_date=tomorrow,
            deductible_end_date=tomorrow,
            operation='cre',
            should_create=False)

        test_loss_case(
            start_date=yesterday,
            end_date=tomorrow,
            deductible_end_date=yesterday,
            operation='cre',
            should_create=True)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
