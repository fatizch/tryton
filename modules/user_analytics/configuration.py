# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSingleton

from trytond.modules.coog_core import model, fields


__all__ = [
    'Configuration',
    ]


class Configuration(ModelSingleton, model.ModelSQL, model.CoogView):
    'Connection Configuration'

    __name__ = 'res.user.analytics.configuration'

    inactivity_limit = fields.Integer('Inactivity Limit Before Logging',
        help='If the user inactivity reaches this limit (in seconds), then the \
        user is considered as inactive', required=True)

    @classmethod
    def default_inactivity_limit(cls):
        return 300
