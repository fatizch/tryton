# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import batch_launcher


def register():
    Pool.register(
        batch_launcher.SelectBatch,
        batch_launcher.BatchParameter,
        module='batch_launcher', type_='model')
    Pool.register(
        batch_launcher.LaunchBatch,
        module='batch_launcher', type_='wizard')
