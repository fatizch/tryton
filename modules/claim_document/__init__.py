from trytond.pool import Pool
from .claim import *
from .document import *
from .benefit import *
from .rule_engine import *


def register():
    Pool.register(
        Benefit,
        DocumentRule,
        LossDescription,
        LossDescriptionDocumentDescriptionRelation,
        Claim,
        DocumentRequest,
        RequestFinder,
        RuleEngineRuntime,
        module='claim_document', type_='model')
