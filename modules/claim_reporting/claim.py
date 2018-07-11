# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.report_engine import Printable

__all__ = [
    'ClaimService',
    ]


class ClaimService(Printable):
    __name__ = 'claim.service'
    __metaclass__ = PoolMeta

    def get_contact(self):
        return self.claim.claimant if self.claim else None

    def get_sender(self):
        return None

    def get_object_for_contact(self):
        return None
