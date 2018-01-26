# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

from trytond.modules.process_cog.process import ProcessFinder, ProcessStart


__metaclass__ = PoolMeta
__all__ = [
    'Process',
    'ContractSetValidateFindProcess',
    'ContractSetValidate',
    ]


class Process:
    __metaclass__ = PoolMeta
    __name__ = 'process'

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('contract_set_validation',
                'Contract Set Validation'))


class ContractSetValidateFindProcess(ProcessStart):
    'ContractSetValidate Find Process'

    __name__ = 'contract.set.validate.find_process'

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'contract.set')])[0].id

    @classmethod
    def build_process_domain(cls):
        return []


class ContractSetValidate(ProcessFinder):
    'Contract Set Validate'

    __name__ = 'contract.set.validate'

    @classmethod
    def get_parameters_model(cls):
        return 'contract.set.validate.find_process'

    @classmethod
    def get_parameters_view(cls):
        return 'process_cog.process_parameters_form'

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ContractSetValidate,
            self).init_main_object_from_process(obj, process_param)
        # TODO : have a contract_set number generator
        return res, errs
