from trytond.pool import Pool

from .batch import *
from .document import *
from .ir import *


def register():
    Pool.register(
        DocumentRequest,
        DocumentRequestLine,
        DocumentReceiveRequest,
        DocumentReceiveAttach,
        DocumentReceiveSetRequests,
        DocumentRequestBatch,
        Attachment,
        module='document_request', type_='model')
    Pool.register(
        DocumentReceive,
        module='document_request', type_='wizard')
