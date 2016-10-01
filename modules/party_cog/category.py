# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import export

__metaclass__ = PoolMeta

__all__ = [
    'PartyCategory',
    ]


class PartyCategory(export.ExportImportMixin):
    __name__ = 'party.category'
