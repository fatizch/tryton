from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Benefit',
    'LossDesc',
    'BenefitRule',
    ]


class Benefit:
    __name__ = 'benefit'

    @classmethod
    def get_beneficiary_kind(cls):
        res = super(Benefit, cls).get_beneficiary_kind()
        res.append(['covered_person', 'Covered Person'])
        return res


class LossDesc:
    __name__ = 'benefit.loss.description'

    @classmethod
    def get_possible_item_kind(cls):
        res = super(LossDesc, cls).get_possible_item_kind()
        res.append(('person', 'Person'))
        return res


class BenefitRule:
    __name__ = 'benefit.rule'

    def get_coverage_amount(self, args):
        if 'option' in args and 'covered_person' in args:
            return args['option'].get_coverage_amount(args['covered_person'])
