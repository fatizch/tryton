# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.api import APIMixin


__all__ = [
    'APIContract',
    ]


class APIContract(APIMixin):
    'API Contract'
    __name__ = 'api.contract'
