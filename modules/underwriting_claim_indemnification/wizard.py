# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'SimulateIndemnificationStart',
    'SimulateIndemnification',
    ]


class SimulateIndemnificationStart(metaclass=PoolMeta):
    __name__ = 'claim.simulate.indemnification.start'

    apply_underwriting_reduction = fields.Boolean(
        'Apply Underwriting Reduction')


class SimulateIndemnification(metaclass=PoolMeta):
    __name__ = 'claim.simulate.indemnification'

    def _create_indemnification(self, service, start_date, end_date,
            previous_indemn):
        indemnification = super(
            SimulateIndemnification, self)._create_indemnification(
            service, start_date, end_date, previous_indemn)

        indemnification.apply_underwriting_reduction = \
            self.start.apply_underwriting_reduction
        return indemnification
