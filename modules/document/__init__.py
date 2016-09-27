# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .document import *
from .attachment import *


def register():
    Pool.register(
        DocumentDescription,
        DocumentReception,
        Attachment,
        ReattachDocument,
        module='document', type_='model')

    Pool.register(
        ReceiveDocument,
        module='document', type_='wizard')
