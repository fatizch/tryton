# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'Process',
    'EndorsementFindProcess',
    'EndorsementStartProcess',
    ]


class Process:
    __name__ = 'process'

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('endorsement_set',
                'Endorsement Set'))


class EndorsementFindProcess:
    __name__ = 'endorsement.start.find_process'

    @fields.depends('contracts', 'model', 'good_process')
    def on_change_contracts(self):
        pool = Pool()
        Model = pool.get('ir.model')
        endorsement_set_model = Model.search([('model', '=',
                    'endorsement.set')])[0].id
        endorsement_model = Model.search([('model', '=',
                    'endorsement')])[0].id

        if not self.contracts:
                self.model = endorsement_model
        else:
            if any([c.contract_set for c in self.contracts]):
                self.model = endorsement_set_model
            else:
                self.model = endorsement_model

        self.good_process = self.on_change_with_good_process()

    @classmethod
    def default_contracts(cls):
        pool = Pool()
        Contract = pool.get('contract')
        contract_ids = super(EndorsementFindProcess, cls).default_contracts()
        all_contracts = []
        for contract_id in contract_ids:
            contract = Contract(contract_id)
            if contract.contract_set:
                all_contracts.extend(contract.contract_set.contracts)
            else:
                all_contracts.append(contract)
        all_contracts = list(set(all_contracts))
        return [c.id for c in all_contracts]


class EndorsementStartProcess:
    __name__ = 'endorsement.start_process'

    @classmethod
    def __setup__(cls):
        super(EndorsementStartProcess, cls).__setup__()
        cls._error_messages.update({
                'same_set_for_all': 'The selected contracts must belong to '
                'the same contract set.',
                })

    def init_main_object_from_process(self, obj, process_param):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        ContractEndorsement = pool.get('endorsement.contract')
        if obj.__name__ == 'endorsement.set':
            if len(set(x.contract_set for x in process_param.contracts)) != 1:
                self.raise_user_error('same_set_for_all')
            obj.endorsements = [Endorsement(
                    effective_date=process_param.effective_date,
                    definition=process_param.definition,
                    state='draft',
                    contract_endorsements=[ContractEndorsement(
                            contract=contract)])
                    for contract in process_param.contracts]
            obj.effective_date = process_param.effective_date
            return True, []
        return super(EndorsementStartProcess,
            self).init_main_object_from_process(obj, process_param)
