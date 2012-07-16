from trytond.pool import Pool
from .party import *
from .contact_mechanism import *


def register():
    Pool.register(
        Party,
        Company,
        Employee,
        Actor,
        Person,
        PersonRelations,
        ContactMechanism,
        module='coop_party', type_='model')
