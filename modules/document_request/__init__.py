# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import batch
from . import document
from . import attachment
from . import report_engine
from . import party


def register():
    Pool.register(
        document.DocumentDescription,
        document.DocumentRequest,
        document.DocumentRequestLine,
        batch.DocumentRequestBatch,
        document.DocumentReception,
        document.ReattachDocument,
        document.ReceiveDocumentLine,
        batch.BatchRemindDocuments,
        attachment.Attachment,
        module='document_request', type_='model')
    Pool.register(
        document.ReceiveDocument,
        party.PartyReplace,
        module='document_request', type_='wizard')
    Pool.register(
        report_engine.ReportGenerate,
        module='document_request', type_='report')
