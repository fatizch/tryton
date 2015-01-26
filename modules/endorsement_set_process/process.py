from trytond.pool import Pool, PoolMeta

from trytond.modules.process_cog import ProcessFinder, ProcessStart


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

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'endorsement.set')])[0].id

    @classmethod
    def build_process_domain(cls):
        return []


class EndorsementSetApply(ProcessFinder):
    'Endorsement Set Apply'

    __name__ = 'endorsement.set.apply'

    @classmethod
    def get_parameters_model(cls):
        return 'endorsement.set.apply.find_process'

    @classmethod
    def get_parameters_view(cls):
        return 'process_cog.process_parameters_form'

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(EndorsementSetApply,
            self).init_main_object_from_process(obj, process_param)
        return res, errs
