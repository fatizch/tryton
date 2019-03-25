# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import utils, fields

__all__ = [
    'Product',
    'OptionDescription',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    def indemnifications_paid_to_subscriber(self):
        # TODO : cache, many models must be modified for clearing to work
        # properly :'(
        kinds = self._get_subscriber_benefit_kinds()
        for coverage in self.coverages:
            for benefit in coverage.benefits:
                if benefit.beneficiary_kind in kinds:
                    return True
        return False

    @classmethod
    def _get_subscriber_benefit_kinds(cls):
        return {'subscriber'}


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    benefits = fields.Many2Many('option.description-benefit', 'coverage',
        'benefit', 'Benefits', states={
            'readonly': ~Eval('start_date'),
            }, domain=[('insurer', '=', Eval('insurer'))],
        depends=['insurer'])

    def get_possible_benefits(self, loss_desc=None, event_desc=None,
            at_date=None):
        res = []
        benefits = utils.get_good_versions_at_date(self, 'benefits', at_date)
        for benefit in benefits:
            if not loss_desc or loss_desc in benefit.loss_descs:
                res.append(benefit)
        return res

    @classmethod
    def _export_light(cls):
        return super(OptionDescription, cls)._export_light() | {'benefits'}
