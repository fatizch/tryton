from trytond.pool import Pool
from .offered import *
from .contract import *
from .document import *
from .report_engine import *


def register():
    Pool.register(
        DocumentRule,
        ReportTemplate,
        RuleDocumentDescriptionRelation,
        Offered,
        OfferedProduct,
        OfferedOptionDescription,
        Contract,
        DocumentRequestLine,
        DocumentRequest,
        DocumentReceiveRequest,
        module='contract_insurance_document_request', type_='model')
