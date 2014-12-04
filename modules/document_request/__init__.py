from trytond.pool import Pool

from .batch import *
from .document import *


def register():
    Pool.register(
        DocumentRequest,
        DocumentRequestLine,
        DocumentReceiveRequest,
        DocumentReceiveAttach,
        DocumentReceiveSetRequests,
        DocumentRequestBatch,
        module='document_request', type_='model')
    Pool.register(
        DocumentReceive,
        module='document_request', type_='wizard')
