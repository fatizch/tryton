from trytond.pool import Pool
from document import *
from wizard import *
from claim import *


def register():
    Pool.register(
        Benefit,
        DocumentRule,
        IndemnificationCalculationResult,
        Claim,
        ClaimIndemnification,
        module='claim_indemnification_document', type_='model')
    Pool.register(
        CreateIndemnification,
        module='claim_indemnification_document', type_='wizard')
