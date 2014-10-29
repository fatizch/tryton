from trytond.pool import Pool
from .document import *


def register():
    Pool.register(
        DocumentRequestLine,
        DocumentRequest,
        DocumentReceiveRequest,
        DocumentReceiveAttach,
        DocumentReceiveSetRequests,
        DocumentRequestBatch,
        module='document_request', type_='model')
    Pool.register(
        DocumentReceive,
        module='document_request', type_='wizard')
