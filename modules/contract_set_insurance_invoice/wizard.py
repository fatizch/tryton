# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import Pool, PoolMeta


__all__ = [
    'Renew',
]


class Renew(metaclass=PoolMeta):
    __name__ = 'contract_term_renewal.renew'

    @classmethod
    def renew_contracts(cls, contracts):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        for contract in contracts:
            if contract.contract_set:
                active_contracts = [c for c in contract.contract_set.contracts
                    if c.status in ['active', 'hold'] and c.activation_history
                    and not c.activation_history[-1].final_renewal]
                if not active_contracts:
                    continue
                max_end_date = max([x.end_date or datetime.date.min
                        for x in active_contracts])
                if not set(active_contracts).issubset(
                        contracts):
                    if contract.end_date >= max_end_date:
                        raise ValidationError(
                            gettext(
                                'contract_set_insurance_invoice'
                                '.msg_must_renew_all',
                                contract_set=contract.contract_set.number))
                    key = 'should_renew_all_%s' % contract.contract_set.number
                    if Warning.check(key):
                        raise UserWarning(key, gettext(
                                'contract_set_insurance_invoice'
                                '.msg_should_renew_all',
                                contract_set=contract.contract_set.number))
        return super(Renew, cls).renew_contracts(contracts)
