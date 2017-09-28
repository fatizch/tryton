# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import underwriting
import process
import event
import wizard


def register():
    Pool.register(
        underwriting.Underwriting,
        process.Process,
        process.ProcessUnderwritingType,
        process.UnderwritingStartFindProcess,
        event.EventTypeAction,
        wizard.ImportProcessSelect,
        module='underwriting_process', type_='model')

    Pool.register(
        process.UnderwritingStart,
        module='underwriting_process', type_='wizard')
