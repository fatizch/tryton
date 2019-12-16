import unittest
import doctest
import datetime

from trytond.pool import Pool
import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_teardown


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'underwriting_claim_indemnification'

    def test0001_underwritings_at_date(self):
        pool = Pool()
        Service = pool.get('claim.service')
        Underwriting = pool.get('underwriting.result')
        service = Service()
        service.underwritings = [
            Underwriting(
                effective_decision_date=datetime.date(2019, 1, 1),
                effective_decision_end=None
                ),
            ]

        # no start, return everything
        res = [u for u in service.underwritings_at_date(None, None)]
        self.assertEqual(len(res), 1)
        res = [u for u in service.underwritings_at_date(None,
                datetime.date(2016, 6, 6))]
        self.assertEqual(len(res), 1)

        # start and end, return if effective_decision_date between those
        res = [u for u in service.underwritings_at_date(
                datetime.date(2018, 1, 1),
                datetime.date(2019, 2, 1))]
        self.assertEqual(len(res), 1)
        res = [u for u in service.underwritings_at_date(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 2, 1))]
        self.assertEqual(len(res), 0)

        # return if start is between decision_date and decision_end
        service.underwritings[0].effective_decision_end = datetime.date(2019,
            12, 24)
        res = [u for u in service.underwritings_at_date(
                datetime.date(2019, 6, 6), None)]
        self.assertEqual(len(res), 1)
        res = [u for u in service.underwritings_at_date(
                datetime.date(2018, 6, 6), None)]
        self.assertEqual(len(res), 0)

        # start and end, return if end is between decision_date and decision_end
        res = [u for u in service.underwritings_at_date(
                datetime.date(2018, 6, 6),
                datetime.date(2019, 6, 6))]
        self.assertEqual(len(res), 1)
        res = [u for u in service.underwritings_at_date(
                datetime.date(2018, 6, 6),
                datetime.date(2018, 7, 6))]
        self.assertEqual(len(res), 0)

        # return if decision_date before end
        service.underwritings[0].effective_decision_end = None
        res = [u for u in service.underwritings_at_date(
                datetime.date(2019, 6, 6),
                datetime.date(2020, 12, 24))]
        self.assertEqual(len(res), 1)
        res = [u for u in service.underwritings_at_date(
                datetime.date(2018, 6, 6),
                datetime.date(2018, 12, 24))]
        self.assertEqual(len(res), 0)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
        'scenario_underwriting_indemnification.rst',
        tearDown=doctest_teardown, encoding='utf8',
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
