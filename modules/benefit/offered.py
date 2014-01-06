from trytond.pool import PoolMeta
from trytond.pyson import Eval, Or

from trytond.modules.coop_utils import fields
from trytond.modules.insurance_product import product

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
            'invisible': Or(~~Eval('is_package'), ~product.IS_INSURANCE),
            }, depends=['currency_digits'])
