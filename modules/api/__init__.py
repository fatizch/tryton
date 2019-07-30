# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

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

    Pool.register_post_init_hooks(add_api_error_handler, module='api')


def add_api_error_handler(pool, update):
    if update:
        return

    from trytond.model import ModelStorage
    from trytond.modules.api import APIErrorHandler

    # Not so good because technically coog_core is more a dependency of api
    # than the opposite, but this makes more sense here, and coog_core will be
    # in the PATH anyway
    from trytond.modules.coog_core import inject_class

    logging.getLogger('modules').info('Adding error handler for APIs')
    inject_class(pool, 'model', ModelStorage, APIErrorHandler)
