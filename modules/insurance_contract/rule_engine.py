from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args
from trytond.modules.coop_utils import utils

__metaclass__ = PoolMeta
__all__ = [
    'OfferedContext',
    'ContractContext',
    ]


class OfferedContext():
    'Offered Context'

    __name__ = 'offered.rule_sets'

    @classmethod
    def get_lowest_level_object(cls, args):
        if 'data' in args:
            return args['data']
        return super(OfferedContext, cls).get_lowest_level_object(args)


class ContractContext():
    'Contract Context'

    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract')
    def _re_relation_number(cls, args, relation_name=None):
        contract = args['contract']
        person = cls.get_person(args)
        subscriber = args['contract'].subscriber
        parties = [x.party for x in utils.get_good_versions_at_date(
                contract, 'covered_elements', args['date'])]
        x = 0
        for party in parties:
            if (not relation_name
                    or party.get_relation_with(subscriber,
                        args['date']) == relation_name):
                x += 1
                if party == person:
                    return x
