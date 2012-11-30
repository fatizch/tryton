from trytond.pool import Pool
from .process_labo import *
from .process import *


def register():
    Pool.register(
        # From process_labo :
        StepDesc,
        StepDescRelation,
        MenuBuilder,
        StepMethodDesc,
        
        # From process :
        RichWorkflow,
        module='process', type_='model')
