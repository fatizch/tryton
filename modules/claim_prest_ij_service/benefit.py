# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.cache import Cache
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

EVENT_DESCS = [
    ('AS', 'Illness'),
    ('AT', 'Work Accident'),
    ('MA', 'Pregnancy'),
    ]

__all__ = [
    'Benefit',
    'EventDesc',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    prest_ij = fields.Boolean('Handle Prest IJ System',
        help='If set, the claims declared using this benefit will be handled '
        'by the Prest IJ system',
        states={'invisible': ~Eval('is_group')}, depends=['is_group'])

    _prest_ij_benefits_cache = Cache('prest_ij_benefits')

    @classmethod
    def create(cls, benefits):
        cls._prest_ij_benefits_cache.clear()
        return super(Benefit, cls).create(benefits)

    @classmethod
    def write(cls, *args):
        super(Benefit, cls).write(*args)
        cls._prest_ij_benefits_cache.clear()

    @classmethod
    def delete(cls, benefits):
        super(Benefit, cls).delete(benefits)
        cls._prest_ij_benefits_cache.clear()

    @classmethod
    def prest_ij_benefits(cls):
        values = cls._prest_ij_benefits_cache.get(None, -1)
        if values != -1:
            return cls.browse(values) if values else []

        benefits = cls.search([('prest_ij', '=', True)])
        cls._prest_ij_benefits_cache.set(None, [x.id for x in benefits])
        return benefits


class EventDesc:
    __metaclass__ = PoolMeta
    __name__ = 'benefit.event.description'

    prest_ij_type = fields.Selection([('', '')] + EVENT_DESCS,
        'Prest IJ Associated Type')

    _prest_ij_event_descs_cache = Cache('prest_ij_event_descs')

    @classmethod
    def create(cls, event_descs):
        cls._prest_ij_event_descs_cache.clear()
        return super(EventDesc, cls).create(event_descs)

    @classmethod
    def write(cls, *args):
        super(EventDesc, cls).write(*args)
        cls._prest_ij_event_descs_cache.clear()

    @classmethod
    def delete(cls, event_descs):
        super(EventDesc, cls).delete(event_descs)
        cls._prest_ij_event_descs_cache.clear()

    @classmethod
    def prest_ij_event_descs(cls, type_):
        values = cls._prest_ij_event_descs_cache.get(type_, -1)
        if values != -1:
            return cls.browse(values) if values else []

        event_descs = cls.search([('prest_ij_type', '=', type_)])
        cls._prest_ij_event_descs_cache.set(type_, [x.id for x in event_descs])
        return event_descs
