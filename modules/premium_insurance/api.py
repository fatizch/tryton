# This file is part of Cojg. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'APIContractUnderwriting',
    ]


class APIContractUnderwriting(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _update_underwriting_convert_option_input(cls, option_data, contract):
        super()._update_underwriting_convert_option_input(option_data,
            contract)
        for extra_premium in option_data['extra_premiums']:
            if extra_premium['mode'] == 'flat':

                # This is the sole mode anyway
                extra_premium['flat_frequency'] = 'yearly'

    @classmethod
    def _update_underwriting_option_extra_premium(cls, extra_premium, data):
        super()._update_underwriting_option_extra_premium(extra_premium, data)

        if 'flat_frequency' in data:
            extra_premium.flat_amount_frequency = data['flat_frequency']
