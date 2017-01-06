# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license
import unittest
import datetime

from trytond.exceptions import UserError
from trytond.pool import Pool

import trytond.tests.test_tryton

from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class WorkDaysTestCase(ModuleTestCase):
    'Work Days Test Case'

    module = 'work_days'

    def create_configuration(self):
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        Holiday = pool.get('work_days.holiday')
        configuration = Configuration(name='Test Configuration',
            code='test_conf')
        configuration.holidays = [
            Holiday(name='christmas', holiday_type='input', month='12',
                day=25),
            Holiday(name='new year', holiday_type='input', month='1', day=1),
            Holiday(holiday_type='easter_holiday', easter_delta_days=1),
            Holiday(name='saturday', holiday_type='weekly_day_off',
                weekly_day='5'),
            Holiday(name='sunday', holiday_type='weekly_day_off',
                weekly_day='6'),
            ]
        configuration.save()

    @with_transaction()
    def test_duplicate_fixed(self):
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        Holiday = pool.get('work_days.holiday')
        fail_fixed = Configuration(name='Fail fixed', code='fail_fixed')
        fail_fixed.holidays = [
            Holiday(name='christmas', holiday_type='input', month='12',
                day=25),
            Holiday(name='christmas', holiday_type='input', month='12',
                day=25),
            ]
        self.assertRaises(UserError, Configuration.save, [fail_fixed])
        self.assertFalse(Configuration.is_duplicate_fixed([]))

    @with_transaction()
    def test_duplicate_easter(self):
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        Holiday = pool.get('work_days.holiday')
        fail_easter = Configuration(name='Fail easter', code='fail_easter')
        fail_easter.holidays = [
            Holiday(holiday_type='easter_holiday', easter_delta_days=1),
            Holiday(holiday_type='easter_holiday', easter_delta_days=1),
            ]
        self.assertRaises(UserError, Configuration.save, [fail_easter])
        self.assertFalse(Configuration.is_duplicate_easter_holiday([]))

    @with_transaction()
    def test_duplicate_weekly(self):
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        Holiday = pool.get('work_days.holiday')
        fail_weekly = Configuration(name='Fail week', code='fail_week')
        fail_weekly.holidays = [
            Holiday(name='saturday', holiday_type='weekly_day_off',
                weekly_day='5'),
            Holiday(name='saturday', holiday_type='weekly_day_off',
                weekly_day='5'),
            ]
        self.assertRaises(UserError, Configuration.save, [fail_weekly])
        self.assertFalse(Configuration.is_duplicate_weekly([]))

    @with_transaction()
    def test_duplicate_holidays(self):
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        Holiday = pool.get('work_days.holiday')
        fail_conf = Configuration(name='Fail conf', code='fail_conf')
        fail_conf.holidays = [
            Holiday(name='christmas', holiday_type='input', month='12',
                day=25),
            Holiday(name='christmas', holiday_type='input', month='12',
                day=25),
            Holiday(holiday_type='easter_holiday', easter_delta_days=1),
            Holiday(holiday_type='easter_holiday', easter_delta_days=1),
            ]
        self.assertRaises(UserError, Configuration.save, [fail_conf])

    @with_transaction()
    def test_weekly_day_off(self):
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        Holiday = pool.get('work_days.holiday')
        dirty_conf = Configuration(name='Dirty Conf', code='dirty_conf')
        dirty_conf.holidays = [
            Holiday(name='monday', holiday_type='weekly_day_off'),
            ]
        self.assertRaises(UserError, Configuration.save, [dirty_conf])

    @with_transaction()
    def test_input_month_day_none(self):
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        Holiday = pool.get('work_days.holiday')
        dirty_conf = Configuration(name='Dirty Conf', code='dirty_conf')
        dirty_conf.holidays = [
            Holiday(holiday_type='input', day=25),
            ]
        self.assertRaises(UserError, Configuration.save, [dirty_conf])
        dirty_conf.holidays = [
            Holiday(holiday_type='input', month='2')
            ]
        self.assertRaises(UserError, Configuration.save, [dirty_conf])

    @with_transaction()
    def test_input_valid_month_day(self):
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        Holiday = pool.get('work_days.holiday')
        dirty_conf = Configuration(name='Dirty Conf', code='dirty_conf')
        dirty_conf.holidays = [
            Holiday(holiday_type='input', day=-2, month='1')
            ]
        self.assertRaises(UserError, Configuration.save, [dirty_conf])
        dirty_conf.holidays = [
            Holiday(holiday_type='input', day=40, month='6')
            ]
        self.assertRaises(UserError, Configuration.save, [dirty_conf])

    @with_transaction()
    def test_input_valid_month_day_combination(self):
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        Holiday = pool.get('work_days.holiday')
        dirty_conf = Configuration(name='Dirty Conf', code='dirty_conf')
        dirty_conf.holidays = [
            Holiday(holiday_type='input', day=30, month='2')
            ]
        for m in ['4', '6', '9', '11']:
            dirty_conf.holidays = [
                Holiday(holiday_type='input', day=31, month=m)
                ]
            self.assertRaises(UserError, Configuration.save,
                [dirty_conf])

    @with_transaction()
    def test_get_weekly_holidays(self):
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        self.create_configuration()
        conf, = Configuration.search([
                ('code', '=', 'test_conf')
                ])
        weekly_holidays = conf.get_weekly_days_off()
        weekly_holidays.sort()
        self.assertEqual(weekly_holidays, ['5', '6'])

    @with_transaction()
    def test_get_fixed_holidays(self):
        self.create_configuration()
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        conf, = Configuration.search([
                ('code', '=', 'test_conf')
                ])
        fixed_holidays = conf.get_fixed_holidays()
        fixed_holidays.sort()
        self.assertEqual(fixed_holidays, [(1, 1), (12, 25)])

    @with_transaction()
    def test_get_easter_holiday(self):
        self.create_configuration()
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        conf, = Configuration.search([
                ('code', '=', 'test_conf')
                ])
        easter_holidays = conf.get_easter_holidays()
        self.assertEqual(easter_holidays, [1])

    @with_transaction()
    def test_final_date(self):
        self.create_configuration()
        pool = Pool()
        Configuration = pool.get('work_days.configuration')
        conf, = Configuration.search([
                ('code', '=', 'test_conf')
                ])
        date = conf.add_workdays(datetime.date(2016, 1, 1), 150)
        self.assertEqual(date, datetime.date(2016, 8, 1))
        sat = conf.add_workdays(datetime.date(2016, 12, 10), 1)
        self.assertEqual(sat, datetime.date(2016, 12, 12))
        skip_weekend = conf.add_workdays(datetime.date(2016, 12, 9), 1)
        self.assertEqual(skip_weekend, datetime.date(2016, 12, 12))
        eas_mon = conf.add_workdays(datetime.date(2016, 3, 25), 1)
        self.assertEqual(eas_mon, datetime.date(2016, 3, 29))
        self.assertRaises(AssertionError, conf.add_workdays,
            datetime.date(2016, 1, 1), -10)
        empty_conf = Configuration(name='Empty Configuration',
            code='empty_conf')
        empty_conf.save()
        final_date = empty_conf.add_workdays(datetime.date(2016, 1, 1), 365)
        self.assertEqual(final_date, datetime.date(2016, 12, 31))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            WorkDaysTestCase))
    return suite
