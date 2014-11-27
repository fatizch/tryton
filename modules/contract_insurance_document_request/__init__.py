from trytond.pool import Pool
from .offered import *
from .contract import *
from .document import *


def register():
    Pool.register(
        DocumentRule,
        DocumentTemplate,
        RuleDocumentDescriptionRelation,
        Offered,
        OfferedProduct,
        OfferedOptionDescription,
        Contract,
        DocumentRequestLine,
        DocumentRequest,
        DocumentReceiveRequest,
        module='contract_insurance_document_request', type_='model')
