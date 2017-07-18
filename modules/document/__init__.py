# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import document
import attachment


def register():
    Pool.register(
        document.DocumentDescription,
        document.DocumentDescGroup,
        document.DocumentReception,
        attachment.Attachment,
        document.ReattachDocument,
        module='document', type_='model')

    Pool.register(
        document.ReceiveDocument,
        module='document', type_='wizard')
