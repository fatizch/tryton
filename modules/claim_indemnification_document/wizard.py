# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields

__all__ = [
    'CreateIndemnification',
    'IndemnificationCalculationResult',
    ]


class IndemnificationCalculationResult:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_calculation_result'

    requested_documents = fields.One2Many('document.request.line', None,
        'Requested Documents')


class CreateIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

    def transition_calculate(self):
        state = super(CreateIndemnification, self).transition_calculate()
        self.result.requested_documents = [r
            for r in self.result.indemnification[0].document_request_lines]
        return state

    def default_result(self, name):
        Indemnification = Pool().get('claim.indemnification')
        defaults = super(CreateIndemnification, self).default_result(name)
        if defaults['indemnification']:
            indemnification = Indemnification(defaults['indemnification'][0])
            defaults['requested_documents'] = [r.id
                for r in indemnification.document_request_lines]
        return defaults

    def transition_regularisation(self):
        DocumentRequest = Pool().get('document.request.line')
        DocumentRequest.save(self.result.requested_documents)
        return super(CreateIndemnification, self).transition_regularisation()
