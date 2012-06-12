from trytond.pool import Pool
from tools import *
from process import *
from process_labo import *


def register():
    Pool.register(
        ProcessState,
        SuspendedProcess,
        DummyObject,
        DummyStep,
        DummyStep1,
        DummyProcessState,
        ProcessDesc,
        StepDesc,
        StepMethodDesc,
        module='insurance_process', type_='model')

    Pool.register(
        CoopProcess,
        ResumeWizard,
        DummyProcess,
        module='insurance_process', type_='wizard')
