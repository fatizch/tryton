# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import utils

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def get_health_complement(cls, args, person):
        if person and person.social_security_dependent:
            parent = person.social_security_dependent[0]
            return cls.get_health_complement(args, parent)
        hc = None
        if person and person.health_complement:
            hc = utils.get_value_at_date(person.health_complement, args['date'])
        if not hc:
            cls.append_error(args, 'Cannot find health complement information')
            return
        return hc

    @classmethod
    def _re_health_hc_system(cls, args):
        person = cls.get_person(args)
        hc = cls.get_health_complement(args, person)
        return hc.hc_system.code if hc and hc.hc_system else ''

    @classmethod
    def _re_health_subscriber_hc_system(cls, args):
        if 'contract' in args:
            person = args['contract'].subscriber
        else:
            person = cls.get_person(args)
        hc = cls.get_health_complement(args, person)
        return hc.hc_system.code if hc and hc.hc_system else ''

    @classmethod
    def _re_health_department(cls, args):
        person = cls.get_person(args)
        hc = cls.get_health_complement(args, person)
        return hc.department if hc else ''

    @classmethod
    def _re_health_subscriber_department(cls, args):
        if 'contract' in args:
            person = args['contract'].subscriber
        else:
            person = cls.get_person(args)
        return person.address_get(at_date=args['date']).get_department()
