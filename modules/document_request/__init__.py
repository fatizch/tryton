# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .batch import *
from .document import *
from .attachment import *
from .report_engine import *
import party


def register():
    Pool.register(
        DocumentRequest,
        DocumentRequestLine,
        DocumentRequestBatch,
        DocumentReception,
        ReattachDocument,
        ReceiveDocumentLine,
        BatchRemindDocuments,
        Attachment,
        module='document_request', type_='model')
    Pool.register(
        ReceiveDocument,
        party.PartyReplace,
        module='document_request', type_='wizard')
    Pool.register(
        ReportGenerate,
        module='document_request', type_='report')
