from trytond.pool import Pool
from utils import *


def register():
    Pool.register(
        DynamicSelection,
        module='coop_utils', type_='model')
