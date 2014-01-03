from trytond.pool import Pool
from .country import *
from .zipcode import *
from .test_case import *


def register():
    Pool.register(
        # From country
        Country,
        CountrySubdivision,
        # From zipcode
        ZipCode,
        # From test_case
        TestCaseModel,
        module='coop_country', type_='model')
