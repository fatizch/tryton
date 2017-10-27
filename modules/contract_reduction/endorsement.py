# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'StartEndorsement',
    ]


class StartEndorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.start'

    @classmethod
    def __setup__(cls):
        super(StartEndorsement, cls).__setup__()
        cls._error_messages.update({
                'reduced_contract': 'Contract %(contract)s has been reduced '
                'since %(date)s, you cannot perform any endorsements on it',
                })

    def check_before_start(self):
        super(StartEndorsement, self).check_before_start()
        if not self.select_endorsement.contract:
            return
        if self.select_endorsement.contract.reduction_date:
            self.raise_user_error('reduced_contract', {
                    'contract': self.select_endorsement.contract.rec_name,
                    'date': str(
                        self.select_endorsement.contract.reduction_date),
                    })
