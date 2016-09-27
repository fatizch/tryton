# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .claim import *
from .document import *
from .benefit import *
from .rule_engine import *
from .report_engine import *


def register():
    Pool.register(
        Benefit,
        DocumentRule,
        LossDescription,
        LossDescriptionDocumentDescriptionRelation,
        Claim,
        DocumentRequest,
        RuleEngineRuntime,
        DocumentRequestLine,
        DocumentReception,
        ReportTemplate,
        module='claim_document', type_='model')

    Pool.register(
        DocumentRequestReport,
        ReceiveDocument,
        module='claim_document', type_='wizard')
