# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import claim
import document
import benefit
import rule_engine
import report_engine


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
        module='claim_document', type_='wizard')
