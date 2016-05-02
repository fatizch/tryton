from trytond.pool import Pool
from .country import *
from .zipcode import *
from .test_case import *


def register():
    Pool.register(
        Country,
        CountrySubdivision,
        Zip,
        TestCaseModel,
        module='country_cog', type_='model')
