# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Party'
]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    @classmethod
    def _invoices_report_contract_key(cls, contract):
        key = super()._invoices_report_contract_key(contract)
        billing_info = contract.billing_information
        key += (billing_info.sepa_mandate, ) if billing_info.sepa_mandate \
            else (False, )
        return key
