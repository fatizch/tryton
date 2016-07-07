# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .offered import *
from .contract import *
from .document import *
from .report_engine import *
from .rule_engine import *


def register():
    Pool.register(
        DocumentRule,
        ReportTemplate,
        RuleDocumentDescriptionRelation,
        Product,
        OptionDescription,
        Contract,
        DocumentRequest,
        DocumentReceiveRequest,
        RuleEngine,
        module='contract_insurance_document_request', type_='model')

    Pool.register(
        ReportGenerate,
        module='contract_insurance_document_request', type_='report')
