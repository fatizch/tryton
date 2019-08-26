# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.exceptions import UserWarning
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.model import Workflow
from trytond.model.exceptions import ValidationError, AccessError
from trytond.modules.coog_core import model


__all__ = [
    'StartEndorsement',
    'Endorsement',
    ]


class StartEndorsement(metaclass=PoolMeta):
    __name__ = 'endorsement.start'

    def check_before_start(self):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        super(StartEndorsement, self).check_before_start()
        if not self.select_endorsement.contract:
            return
        if self.select_endorsement.contract.reduction_date:
            endorsement_def = self.select_endorsement.endorsement_definition
            # In the case where the endorsement we want to apply is
            # a terminate contract, we will authorize it by displaying
            # a warning message otherwise we block others endorsements
            if len(endorsement_def.endorsement_parts) == 1:
                endorsement_part = endorsement_def.endorsement_parts[0]
                if endorsement_part.view == 'terminate_contract':
                    key = 'terminate_reduced_contract'
                    if Warning.check(key):
                        raise UserWarning(key, gettext(
                                'contract_reduction'
                                '.msg_terminate_reduced_contract',
                                contract=self.select_endorsement
                                .contract.rec_name,
                                date=self.select_endorsement
                                .contract.reduction_date))
            else:
                raise ValidationError(gettext(
                        'contract_reduction.msg_reduced_contract',
                        contract=self.select_endorsement.contract.rec_name,
                        date=self.select_endorsement.contract.reduction_date))


class Endorsement(metaclass=PoolMeta):
    __name__ = 'endorsement'

    @classmethod
    @model.CoogView.button
    @Workflow.transition('canceled')
    def cancel(cls, endorsements):
        all_contracts = sum([list(x.contracts or []) for x in endorsements], [])
        reduced = [x for x in all_contracts if x.reduction_date]
        if reduced:
            raise AccessError(gettext(
                    'contract_reduction.msg_no_cancellation_on_reduced',
                    contracts='\n'.join(x.contract_number for x in reduced)))
        super(Endorsement, cls).cancel(endorsements)
