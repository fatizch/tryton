# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import resource
from . import api


def register():
    Pool.register(
        resource.WebUIResource,
        resource.WebUIResourceKey,
        resource.RelationWebUIResourceKeyIRModel,
        api.APICore,
        module='web_configuration', type_='model',
    )
