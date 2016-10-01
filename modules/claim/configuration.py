# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import model
from trytond.model import ModelSingleton


__all__ = [
    'Configuration'
    ]


class Configuration(ModelSingleton, model.CoogSQL, model.CoogView):
    'Claim Configuration'

    __name__ = 'claim.configuration'
