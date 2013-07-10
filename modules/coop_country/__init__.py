from trytond.pool import Pool
from trytond.modules.coop_utils import export
from .zipcode import *


def register():
    Pool.register(
        Country,
        ZipCode,
        module='coop_country', type_='model')

    export.add_export_to_model([
            ('country.subdivision', ('code',)),
            ], 'coop_country')
