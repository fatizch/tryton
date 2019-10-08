# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import offered
from . import contract
from . import document
from . import report_engine
from . import rule_engine
from . import wizard
from . import api
from . import event


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
        event.EventLog,
        module='contract_insurance_document_request', type_='model',
        depends=['event_log'])

    Pool.register(
        api.ContractApi,
        api.CoveredElementApi,
        api.APIParty,
        api.APIContract,
        module='contract_insurance_document_request', type_='model',
        depends=['api'])

    Pool.register(
        document.ReceiveDocument,
        wizard.PartyErase,
        module='contract_insurance_document_request', type_='wizard')
