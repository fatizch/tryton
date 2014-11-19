from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

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
            }, depends=['currency_digits'])
