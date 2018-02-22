# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import Workflow
from trytond.modules.coog_core import model


__all__ = [
    'StartEndorsement',
    'Endorsement',
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


class Endorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement'

    @classmethod
    def __setup__(cls):
        super(Endorsement, cls).__setup__()
        cls._error_messages.update({
                'no_cancellation_on_reduced':
                'The following contracts are reduced:\n\n%(contracts)s\n\n'
                'You cannot cancel endorsements on reduced contracts.'
                })

    @classmethod
    @model.CoogView.button
    @Workflow.transition('canceled')
    def cancel(cls, endorsements):
        all_contracts = sum([list(x.contracts or []) for x in endorsements], [])
        reduced = [x for x in all_contracts if x.reduction_date]
        if reduced:
            cls.raise_user_error('no_cancellation_on_reduced',
                {'contracts': '\n'.join([x.contract_number for x in reduced])})
        super(Endorsement, cls).cancel(endorsements)