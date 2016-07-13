# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .batch import *
from .document import *
from .attachment import *
from .report_engine import *


def register():
    Pool.register(
        DocumentRequest,
        DocumentRequestLine,
        DocumentReceiveRequest,
        DocumentReceiveAttach,
        DocumentReceiveSetRequests,
        DocumentRequestBatch,
        BatchRemindDocuments,
        Attachment,
        module='document_request', type_='model')
    Pool.register(
        DocumentReceive,
        module='document_request', type_='wizard')
    Pool.register(
        ReportGenerate,
        module='document_request', type_='report')
