# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import offered
import contract
import document
import report_engine
import rule_engine


def register():
    Pool.register(
        offered.DocumentRule,
        report_engine.ReportTemplate,
        offered.RuleDocumentDescriptionRelation,
        offered.Product,
        offered.OptionDescription,
        contract.Contract,
        document.DocumentRequest,
        document.DocumentReception,
        rule_engine.RuleEngine,
        rule_engine.RuleEngineRuntime,
        document.DocumentRequestLine,
        module='contract_insurance_document_request', type_='model')

    Pool.register(
        document.ReceiveDocument,
        module='contract_insurance_document_request', type_='wizard')
