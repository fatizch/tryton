from trytond.pool import Pool
from trytond.modules.coop_utils import export
from .zipcode import *
from .test_case import *


def register():
    Pool.register(
        Country,
        ZipCode,
        # form test_case
        TestCaseModel,
        module='coop_country', type_='model')

    export.add_export_to_model([
            ('country.subdivision', ('code',)),
            ], 'coop_country')
