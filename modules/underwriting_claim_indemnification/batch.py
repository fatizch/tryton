# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

__all__ = [
    'SimulateIndemnificationBatch',
    ]


class SimulateIndemnificationBatch(metaclass=PoolMeta):
    __name__ = 'claim.indemnification.simulate'

    @classmethod
    def _get_simulation_wizard(cls, treatment_date, **kwargs):
        wiz = super(SimulateIndemnificationBatch, cls)._get_simulation_wizard(
            treatment_date, **kwargs)
        wiz.start.apply_underwriting_reduction = kwargs.get(
            'apply_underwriting_commission', False)
        return wiz
