from trytond.pool import Pool
from party import *


def register():
    Pool.register(
        Party,
        Actor,
        PersonRelations,
        Person,
        LegalEntity,
        Insurer,
        Broker,
        module='insurance_party', type_='model')
