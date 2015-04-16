from trytond.pool import Pool, PoolMeta

from trytond.modules.process_cog import ProcessFinder, ProcessStart
from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'Process',
    'EndorsementSetApplyFindProcess',
    'EndorsementSetApply',
    ]


class Process:
    __name__ = 'process'

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('endorsement_set_application',
                'Endorsement Set Application'))


class EndorsementSetApplyFindProcess(ProcessStart):
    'EndorsementSetApply Find Process'

    __name__ = 'endorsement.set.apply.find_process'

    effective_date = fields.Date('Effective Date', required=True)
    contract_set = fields.Many2One('contract.set', 'Contract Set',
        required=True)
    endorsement_set = fields.Many2One('endorsement.set', 'Endorsement Set')
    endorsement_definition = fields.Many2One('endorsement.definition',
        'Endorsement Definition', required=True)

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'endorsement.set')])[0].id


class EndorsementSetApply(ProcessFinder):
    'Endorsement Set Apply'

    __name__ = 'endorsement.set.apply'

    @classmethod
    def get_parameters_model(cls):
        return 'endorsement.set.apply.find_process'

    @classmethod
    def get_parameters_view(cls):
        return \
            'endorsement_set_process.endorsement_set_apply_find_process_form'

    def init_main_object_from_process(self, obj, process_param):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        ContractEndorsement = pool.get('endorsement.contract')
        res, errs = super(EndorsementSetApply,
            self).init_main_object_from_process(obj, process_param)
        obj.endorsements = [Endorsement(
                effective_date=process_param.effective_date,
                definition=process_param.endorsement_definition,
                contract_endorsements=[ContractEndorsement(contract=contract)])
                for contract in process_param.contract_set.contracts]
        return res, errs
