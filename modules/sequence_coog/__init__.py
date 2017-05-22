# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

import sequence


def register():
    Pool.register(
        sequence.Sequence,
        sequence.SequenceStrict,
        module='sequence_coog', type_='model')
