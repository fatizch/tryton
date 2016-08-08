# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .batch_launcher import *


def register():
    Pool.register(
        SelectBatch,
        BatchParameter,
        module='batch_launcher', type_='model')
    Pool.register(
        LaunchBatch,
        module='batch_launcher', type_='wizard')
