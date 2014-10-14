from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args
from trytond.modules.cog_utils import utils

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def get_lowest_level_object(cls, args):
        if 'option' in args:
            return args['option']
        return super(RuleEngineRuntime, cls).get_lowest_level_object(args)

    @classmethod
    @check_args('contract')
    def _re_relation_number(cls, args, relation_name=None):
        contract = args['contract']
        person = cls.get_person(args)
        subscriber = args['contract'].subscriber
        parties = [x.party for x in utils.get_good_versions_at_date(
                contract, 'covered_elements', args['date'])]
        parties.sort(key=lambda x: x.birth_date)
        x = 0
        for party in parties:
            kinds = [rel.type.code for rel in
                utils.get_good_versions_at_date(party, 'relations',
                    args['date']) if rel.to.id == subscriber.id]
            if not relation_name or relation_name in kinds:
                x += 1
                if party == person:
                    return x
        return x

    @classmethod
    def _re_number_of_covered_with_relation(cls, args, relation_name=None):
        contract = args['contract']
        subscriber = args['contract'].subscriber
        parties = [x.party for x in utils.get_good_versions_at_date(
                contract, 'covered_elements', args['date']) if x.party]
        res = 0
        for party in parties:
            kinds = [rel.type.code for rel in
                utils.get_good_versions_at_date(party, 'relations',
                    args['date']) if rel.to.id == subscriber.id]
            if not relation_name or relation_name in kinds:
                res += 1
        return res
