# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from lxml import etree

from trytond.pool import PoolMeta
from trytond.tools import memoize


__all__ = [
    'View',
    ]


class View:
    __metaclass__ = PoolMeta
    __name__ = 'ir.ui.view'

    @classmethod
    @memoize(10)
    def get_rng(cls, type_):
        rng = super(View, cls).get_rng(type_)
        if type_ == 'form':
            widgets = rng.xpath(
                '//ns:define/ns:optional/ns:attribute'
                '[@name="widget"]/ns:choice',
                namespaces={'ns': 'http://relaxng.org/ns/structure/1.0'})[0]
            subelem = etree.SubElement(widgets,
                '{http://relaxng.org/ns/structure/1.0}value')
            subelem.text = 'source'
        return rng
