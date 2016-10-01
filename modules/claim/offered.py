# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import utils, fields

__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    ]


class OptionDescription:
    __name__ = 'offered.option.description'

    benefits = fields.Many2Many('option.description-benefit', 'coverage',
        'benefit', 'Benefits', context={
            'start_date': Eval('start_date'),
            'currency_digits': Eval('currency_digits'),
            }, states={
            'readonly': ~Eval('start_date'),
            }, depends=['currency_digits', 'start_date'])

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
