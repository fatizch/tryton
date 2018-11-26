# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import claim
from . import document
from . import benefit
from . import rule_engine
from . import report_engine
from . import wizard


def register():
    Pool.register(
        benefit.Benefit,
        benefit.DocumentRule,
        benefit.LossDescription,
        benefit.LossDescriptionDocumentDescriptionRelation,
        claim.Claim,
        document.DocumentRequest,
        rule_engine.RuleEngineRuntime,
        document.DocumentRequestLine,
        document.DocumentReception,
        report_engine.ReportTemplate,
        module='claim_document', type_='model')

    Pool.register(
        report_engine.DocumentRequestReport,
        document.ReceiveDocument,
        wizard.PartyErase,
        module='claim_document', type_='wizard')
