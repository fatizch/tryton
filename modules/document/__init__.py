from trytond.pool import Pool
from .document import *
from .attachment import *


def register():
    Pool.register(
        DocumentDescription,
        Attachment,
        module='document', type_='model')
