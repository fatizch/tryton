# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args


__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('date')
    def _re_employment_gross_salary(cls, args):
        at_date = args['date']
        return cls.get_person(args).get_employment_version_data(
            'gross_salary', at_date)

    @classmethod
    @check_args('contract', 'date')
    def _re_subscriber_employment_gross_salary(cls, args):
        at_date = args['date']
        return args['contract'].subscriber.get_employment_version_data(
            'gross_salary', at_date)

    @classmethod
    @check_args('date')
    def _re_employment_gross_salary_1st_january(cls, args):
        at_date = datetime.date(args['date'].year, 1, 1)
        return cls.get_person(args).get_employment_version_data(
            'gross_salary', at_date)

    @classmethod
    @check_args('contract', 'date')
    def _re_subscriber_employment_gross_salary_1st_january(cls, args):
        at_date = datetime.date(args['date'].year, 1, 1)
        return args['contract'].subscriber.get_employment_version_data(
            'gross_salary', at_date)

    @classmethod
    @check_args('date')
    def _re_employment_work_time_type_code(cls, args):
        at_date = args['date']
        work_time_type = cls.get_person(args).get_employment_version_data(
            'work_time_type', at_date)
        return work_time_type.code if work_time_type else ''
