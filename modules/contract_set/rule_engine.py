import collections

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
    @check_args('contract')
    def _re_relation_number_order_by_age_in_set(cls, args, relation_name):
        if 'contract_set' in args:
            contract_set = args['contract_set']
        else:
            main_contract = args['contract']
            contract_set = main_contract.contract_set
        if not contract_set:
            return cls._re_relation_number_order_by_age(cls, args,
                relation_name)
        person = cls.get_person(args)
        parties = []
        res = 0
        for contract in contract_set.contracts:
            parties.extend([x.party for x in utils.get_good_versions_at_date(
                        contract, 'covered_elements', args['date'])])
        parties.sort(key=lambda x: x.birth_date)
        relation_number = collections.defaultdict(int)
        for party in parties:
            relations = [rel for rel in
                utils.get_good_versions_at_date(party, 'relations',
                    args['date'])]
            for relation in relations:
                if (relation.to in parties and
                        relation.type.code == relation_name):
                    relation_number[relation.to] += 1
                    if party == person:
                        res = max(res, relation_number[relation.to])
            if party == person:
                return res
        return 0

    @classmethod
    def _re_number_of_covered_with_relation_in_set(cls, args,
            relation_name):
        if 'contract_set' in args:
            contract_set = args['contract_set']
        else:
            main_contract = args['contract']
            contract_set = main_contract.contract_set
        if not contract_set:
            return cls._re_number_of_covered_with_relation(cls, args,
                relation_name)
        parties = []
        number_of_covered = 0
        for contract in contract_set.contracts:
            parties.extend([x.party for x in utils.get_good_versions_at_date(
                contract, 'covered_elements', args['date'])])
        for party in parties:
            for relation in utils.get_good_versions_at_date(party, 'relations',
                    args['date']):
                if (relation.to in parties and
                        relation.type.code == relation_name):
                    number_of_covered += 1
                    break
        return number_of_covered
