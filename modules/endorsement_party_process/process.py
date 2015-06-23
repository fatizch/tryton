from trytond.modules.process_cog import ProcessFinder, ProcessStart
from trytond.modules.cog_utils import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

__metaclass__ = PoolMeta

__all__ = [
    'Process',
    'EndorsementPartyFindProcess',
    'EndorsementPartyStartProcess',
    'EndorsementFindProcess',
    ]


class Process:
    __name__ = 'process'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('party_endorsement', 'Party Endorsement'))


class EndorsementPartyFindProcess(ProcessStart):
    'Endorsement Party Process Finder'

    __name__ = 'endorsement_party.start.find_process'

    effective_date = fields.Date('Effective Date', required=True)
    definition = fields.Many2One('endorsement.definition',
        'Endorsement Definition', required=True, domain=[
            ('is_party', '=', True)])
    party = fields.Many2One('party.party', 'Party', required=True)

    @classmethod
    def default_model(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        return Model.search([('model', '=', 'endorsement')])[0].id

    @classmethod
    def build_process_domain(cls):
        return [('on_model', '=', Eval('model')),
            ('kind', '=', 'party_endorsement')]


class EndorsementPartyStartProcess(ProcessFinder):
    'Endorsement Start Process'

    __name__ = 'endorsement_party.start_process'

    @classmethod
    def get_parameters_model(cls):
        return 'endorsement_party.start.find_process'

    @classmethod
    def get_parameters_view(cls):
        return 'endorsement_party_process.' + \
            'endorsement_party_start_process_find_process_view_form'

    def init_main_object_from_process(self, obj, process_param):
        pool = Pool()
        PartyEndorsement = pool.get('endorsement.party')
        res, errs = super(EndorsementPartyStartProcess,
            self).init_main_object_from_process(obj, process_param)
        obj.effective_date = process_param.effective_date
        obj.definition = process_param.definition
        obj.party_endorsements = [PartyEndorsement(party=process_param.party)]
        return res, errs


class EndorsementFindProcess:
    __name__ = 'endorsement.start.find_process'

    @classmethod
    def __setup__(cls):
        super(EndorsementFindProcess, cls).__setup__()
        cls.definition.domain.extend([('is_party', '=', False)])
