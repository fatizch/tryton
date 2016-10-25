# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .event import *


def register():
    Pool.register(
        EventTypeAction,
        module='event_email', type_='model')
