from trytond.pool import Pool
from .benefit import *


def register():
    Pool.register(
        LossDescription,
        MedicalActDescription,
        MedicalActFamily,
        module='benefit_health', type_='model')
