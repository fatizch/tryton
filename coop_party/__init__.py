from trytond.pool import Pool
from .party import *
from .contact_mechanism import *


def register():
    Pool.register(
        Party,
        Actor,
        PersonRelations,
        Person,
        LegalEntity,
        ContactMechanism,
        module='coop_party', type_='model')
