# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args
from trytond.modules.coog_core import utils

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract')
    def _re_relation_number_order_by_age(cls, args, relation_name):
        contract = args['contract']
        date = args['date']
        person = cls.get_person(args)
        subscriber = args['contract'].subscriber
        parties = [x.party for x in contract.covered_elements
            if x.party and x.is_covered_at_date(date)]
        parties.sort(key=lambda x: x.birth_date)
        x = 0
        for party in parties:
            kinds = [rel.type.code for rel in
                utils.get_good_versions_at_date(party, 'relations', date)
                if rel.to.id == subscriber.id]
            if relation_name in kinds:
                x += 1
                if party == person:
                    return x
        return x

    @classmethod
    def _re_number_of_covered_with_relation(cls, args, relation_name):
        contract = args['contract']
        date = args['date']
        parties = [x.party for x in contract.covered_elements
            if x.party and x.is_covered_at_date(date)]
        number_of_covered = 0
        for party in parties:
            for relation in utils.get_good_versions_at_date(party, 'relations',
                    date):
                if (relation.to in parties and
                        relation.type.code == relation_name):
                    number_of_covered += 1
                    break
        return number_of_covered
