from trytond.pool import Pool
from .document import *


def register():
    Pool.register(
        DocumentDescription,
        module='document', type_='model')
