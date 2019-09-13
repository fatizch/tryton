# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import api
from . import ir
from . import res

from .api.core import *  # NOQA required for easy availability


def register():
    Pool.register(
        api.core.APIModel,
        api.core.APICore,
        ir.APIAccess,
        res.Group,
        res.UserGroup,
        module='api', type_='model')
