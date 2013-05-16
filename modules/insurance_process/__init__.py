from trytond.pool import Pool
from process import *
from process_labo import *


def register():
    Pool.register(
        # ProcessState,
        # SuspendedProcess,
        # ProcessDesc,
        # StepDesc,
        # StepMethodDesc,
        module='insurance_process', type_='model')

    Pool.register(
        # CoopProcess,
        # ResumeWizard,
        module='insurance_process', type_='wizard')
