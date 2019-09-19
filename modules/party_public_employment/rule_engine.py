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
    def _re_employment_increased_index(cls, args):
        at_date = args['date']
        return cls.get_person(args).get_employment_version_data(
            'increased_index', at_date)

    @classmethod
    @check_args('date')
    def _re_employment_gross_index(cls, args):
        at_date = args['date']
        return cls.get_person(args).get_employment_version_data(
            'gross_index', at_date)

    @classmethod
    @check_args('contract', 'date')
    def _re_subscriber_employment_increased_index(cls,
            args):
        at_date = args['date']
        return args['contract'].subscriber.get_employment_version_data(
            'increased_index', at_date)

    @classmethod
    @check_args('contract', 'date')
    def _re_subscriber_employment_gross_index(cls, args):
        at_date = args['date']
        return args['contract'].subscriber.get_employment_version_data(
            'gross_index', at_date)

    @classmethod
    @check_args('date')
    def _re_employment_increased_index_1st_january(cls, args):
        at_date = datetime.date(args['date'].year, 1, 1)
        return cls.get_person(args).get_employment_version_data(
            'increased_index', at_date)

    @classmethod
    @check_args('date')
    def _re_employment_gross_index_1st_january(cls, args):
        at_date = datetime.date(args['date'].year, 1, 1)
        return cls.get_person(args).get_employment_version_data(
            'gross_index', at_date)

    @classmethod
    @check_args('contract', 'date')
    def _re_subscriber_employment_increased_index_1st_january(cls,
            args):
        at_date = datetime.date(args['date'].year, 1, 1)
        return args['contract'].subscriber.get_employment_version_data(
            'increased_index', at_date)

    @classmethod
    @check_args('contract', 'date')
    def _re_subscriber_employment_gross_index_1st_january(cls, args):
        at_date = datetime.date(args['date'].year, 1, 1)
        return args['contract'].subscriber.get_employment_version_data(
            'gross_index', at_date)

    @classmethod
    @check_args('date')
    def _re_civil_service_employment_entry_date(cls, args):
        return cls.get_person(args).civil_service_employment_entry_date()

    @classmethod
    @check_args('date')
    def _re_administrative_situation(cls, args):
        return cls.get_person(args).administrative_situation_at_date(
            args['date'])

    @classmethod
    @check_args('date')
    def _re_administrative_situation_sub_status(cls, args):
        return cls.get_person(args).\
            administrative_situation_sub_status_at_date(args['date'])

    @classmethod
    @check_args('contract', 'date')
    def _re_subscriber_civil_service_employment_entry_date(cls, args):
        return args['contract'].subscriber.civil_service_employment_entry_date()

    @classmethod
    @check_args('contract', 'date')
    def _re_subscriber_administrative_situation(cls, args):
        return args['contract'].subscriber.administrative_situation_at_date(
            args['date'])

    @classmethod
    @check_args('contract', 'date')
    def _re_subscriber_administrative_situation_sub_status(cls, args):
        return args['contract'].subscriber.\
            administrative_situation_sub_status_at_date(args['date'])
