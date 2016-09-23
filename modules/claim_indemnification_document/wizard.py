from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__all__ = [
    'CreateIndemnification',
    'IndemnificationCalculationResult',
    ]


class IndemnificationCalculationResult:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_calculation_result'

    requested_documents = fields.Many2Many(
        'document.request.line', None, None, 'Requested Documents',
        readonly=True)


class CreateIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

    def transition_calculate(self):
        service = self.definition.service
        args = {}
        args['start_date'] = self.definition.start_date
        args['end_date'] = self.definition.end_date
        service.init_dict_for_rule_engine(args)
        res = service.benefit.calculate_required_docs_for_indemnification(args)
        state = super(CreateIndemnification, self).transition_calculate()
        if not res:
            return state
        requested = \
            self.result.indemnification[0].create_required_documents(res)
        self.doc_requests = [r.id for r in requested]
        return state

    def default_result(self, name):
        defaults = super(CreateIndemnification, self).default_result(name)
        requested = getattr(self, 'doc_requests', None)
        if requested:
            defaults['requested_documents'] = requested
        return defaults
