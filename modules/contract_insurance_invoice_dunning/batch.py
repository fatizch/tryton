from trytond.pool import PoolMeta

__all__ = [
    'DunningTreatmentBatch',
    ]


class DunningTreatmentBatch:
    __metaclass__ = PoolMeta
    __name__ = 'account.dunning.treat'

    @classmethod
    def get_batch_domain(cls, treatment_date, extra_args):
        return super(DunningTreatmentBatch, cls).get_batch_domain(
            treatment_date, extra_args) + [
            ('is_contract_main', '=', True)]
