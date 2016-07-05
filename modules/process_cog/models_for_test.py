# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.process_cog import CogProcessFramework

__all__ = [
    'ModelProcess'
    ]


class ModelProcess(CogProcessFramework):
    'Test Model Process'
    __name__ = 'process.test.model'
