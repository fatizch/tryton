from trytond.pool import PoolMeta

from trytond.modules.cog_utils import utils

__metaclass__ = PoolMeta
__all__ = [
    'Benefit',
    'LossDescription',
    'BenefitRule',
    ]


class Benefit:
    __name__ = 'benefit'

    @classmethod
    def get_beneficiary_kind(cls):
        res = super(Benefit, cls).get_beneficiary_kind()
        res.append(['covered_person', 'Covered Person'])
        return res


class LossDescription:
    __name__ = 'benefit.loss.description'

    @classmethod
    def __setup__(cls):
        utils.update_selection(cls, 'item_kind', [('person', 'Person')])
        super(LossDescription, cls).__setup__()


class BenefitRule:
    __name__ = 'benefit.rule'

    def get_coverage_amount(self, args):
        if 'option' in args and 'covered_person' in args:
            return args['option'].get_coverage_amount(args['covered_person'])
