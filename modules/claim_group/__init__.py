from trytond.pool import Pool
from .offered import *
from .benefit import *


def register():
    Pool.register(
        OptionDescription,
        Benefit,
        module='claim_group', type_='model')
