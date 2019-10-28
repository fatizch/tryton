# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

import trytond.tests.test_tryton
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'event_log'

    def test0085_check_overriden_event_rollback(self):
        Event = Pool().get('event')

        # Should fail because event code does not exist
        self.assertRaises(ValueError, Event.notify_events, [1, 2, 3, 4],
            'non_existing_event_code')

        with Transaction().set_context(_will_be_rollbacked=True):
            # It's alright, the code will not be triggered anyway
            Event.notify_events([1, 2, 3, 4], 'non_existing_event_code')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
