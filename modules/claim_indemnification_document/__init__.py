# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from benefit import *
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
