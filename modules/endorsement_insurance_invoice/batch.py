from trytond.pool import Pool
from trytond.modules.coog_core import batch

__all__ = [
    'RecalculateEndorsementBatch',
    ]


class RecalculateEndorsementBatch(batch.BatchRoot):
    'Recalculate Endorsement Batch'

    __name__ = 'endorsement.recalculate.batch'

    @classmethod
    def __setup__(cls):
        super(RecalculateEndorsementBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                })

    @classmethod
    def parse_params(cls, params):
        params = super(RecalculateEndorsementBatch, cls).parse_params(params)
        assert params.get('job_size') == 0
        return params

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def select_ids(cls, treatment_date, ids_list):
        return [(int(x),) for x in ids_list[1:-1].split(',')]

    @classmethod
    def init_endorsement(cls, contract, effective_date):
        pool = Pool()
        EndorsementDefinition = pool.get('endorsement.definition')
        Endorsement = pool.get('endorsement')
        EndorsementContract = pool.get('endorsement.contract')
        recalculate_def = EndorsementDefinition.get_definition_by_code(
            'recalculate_and_reinvoice_contract')
        endorsement = Endorsement()
        endorsement.effective_date = effective_date
        endorsement.definition = recalculate_def
        endorsement.contract_endorsements = [
            EndorsementContract(contract=contract)]
        return endorsement

    @classmethod
    def execute(cls, objects, ids, treatment_date, ids_list):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        all_endorsements = []
        for contract in objects:
            all_endorsements.append(cls.init_endorsement(contract,
                    treatment_date))
        Endorsement.save(all_endorsements)
        Endorsement.apply(all_endorsements)
        return ids
