import unittest
import datetime

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework
from trytond.modules.cog_utils import utils, coop_date


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'cog_utils'

    def test0020get_module_path(self):
        self.assert_(utils.get_module_path('cog_utils'))
        self.assert_(utils.get_module_path('dfsfsfsdf') is None)

    def test0030calculate_duration_between(self):
        start_date = datetime.date(2013, 1, 1)
        end_date = datetime.date(2013, 1, 31)
        self.assert_(coop_date.duration_between(start_date, end_date, 'day')
            == 31)
        self.assert_(coop_date.duration_between(start_date, end_date, 'month')
            == 1)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (1, True))
        self.assert_(coop_date.duration_between(start_date, end_date,
                'quarter') == 0)
        self.assert_(coop_date.duration_between(start_date, end_date, 'year')
            == 0)

        end_date = datetime.date(2013, 3, 31)
        self.assert_(coop_date.duration_between(start_date, end_date, 'day')
            == 90)
        self.assert_(coop_date.duration_between(start_date, end_date, 'month')
            == 3)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (3, True))
        self.assert_(coop_date.duration_between(start_date, end_date,
                'quarter') == 1)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'quarter') == (1, True))
        self.assert_(coop_date.duration_between(start_date, end_date, 'year')
            == 0)

        end_date = datetime.date(2013, 12, 31)
        self.assert_(coop_date.duration_between(start_date, end_date, 'day')
            == 365)
        self.assert_(coop_date.duration_between(start_date, end_date, 'month')
            == 12)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (12, True))
        self.assert_(coop_date.duration_between(start_date, end_date,
            'quarter') == 4)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'quarter') == (4, True))
        self.assert_(coop_date.duration_between(start_date, end_date, 'year')
            == 1)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'year') == (1, True))

        end_date = datetime.date(2014, 1, 1)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (12, False))
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'year') == (1, False))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
