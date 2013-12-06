from trytond.pool import Pool
from .endorsement import *
from .product import *
from .wizard import *


def register():
    Pool.register(
        # From product
        EndorsementTemplate,
        Product,
        EndorsementTemplateProductRelation,
        # From endorsement
        Contract,
        ContractOption,
        Endorsement,
        EndorsementField,
        EndorsementOption,
        EndorsementOptionField,
        # From wizard
        EndorsementSelection,
        module='endorsement', type_='model')

    Pool.register(
        # From wizard
        EndorsementLauncher,
        module='endorsement', type_='wizard')
