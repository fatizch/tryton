from trytond.pool import Pool
from .benefit import *


def register():
    Pool.register(
        LossDescription,
        MedicalActFamily,
        MedicalActDescription,
        module='benefit_health', type_='model')
