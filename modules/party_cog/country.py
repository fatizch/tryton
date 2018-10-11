# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval
from trytond.cache import Cache
from trytond.model import DictSchemaMixin

from trytond.modules.coog_core import model, fields

__all__ = [
    'Country',
    'CountryAddressLine',
    ]


class Country:
    __metaclass__ = PoolMeta
    __name__ = 'country.country'

    address_line_configuration = fields.Function(
        fields.Boolean('Address Line Configuration'),
        'get_address_line_configuration', 'setter_void')
    address_lines = fields.One2Many('country.address.line', 'country',
        'Address Lines', states={
            'invisible': ~Eval('address_line_configuration'),
            'required': Bool(Eval('address_line_configuration', False))},
        depends=['address_line_configuration'])

    _address_line_cache = Cache('get_country_address_lines_cache')

    @classmethod
    def setter_void(cls, *args, **kwargs):
        pass

    def get_address_line_configuration(self, name):
        return bool(self.address_lines)

    def get_address_lines(self):
        cached = self.__class__._address_line_cache.get(self.id, None)
        if cached is not None:
            return cached
        address_lines = [x.name for x in self.address_lines]
        self.__class__._address_line_cache.set(self.id, address_lines)
        return address_lines


class CountryAddressLine(DictSchemaMixin, model.CoogSQL, model.CoogView):
    'Country Address Line'

    __name__ = 'country.address.line'

    country = fields.Many2One('country.country', 'Country', required=True,
        select=True, ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(CountryAddressLine, cls).__setup__()
        cls.string.string = 'Label'
        cls.name.string = 'Code'
        cls.type_.selection = [('char', 'Char')]
        cls.type_.states['invisible'] = True
        cls._order = [('name', 'ASC')]

    @classmethod
    def default_type_(cls):
        return 'char'

    @classmethod
    def create(cls, vlist):
        country = Pool().get('country.country')
        vals = super(CountryAddressLine, cls).create(vlist)
        country._address_line_cache.clear()
        return vals

    @classmethod
    def write(cls, *args):
        country = Pool().get('country.country')
        super(CountryAddressLine, cls).write(*args)
        country._address_line_cache.clear()

    @classmethod
    def delete(cls, instances):
        country = Pool().get('country.country')
        super(CountryAddressLine, cls).delete(instances)
        country._address_line_cache.clear()
