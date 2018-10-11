# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.config import config

from trytond.modules.coog_core import fields

__all__ = [
    'Party',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    connection_url = fields.Function(fields.Char('Connection Url'),
        'get_connection_url')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._error_messages.update({
                'no_token': 'No token for this party: %s',
                'no_request_hash': 'No request hash or expired hash for this'
                ' token: %s',
                'no_app_conf': 'App url not configurated',
                })

    def create_validation_hash(self):
        pool = Pool()
        Token = pool.get('api.token')
        Token.create_request_hash([self.id])

    def get_connection_url(self, name):
        pool = Pool()
        Token = pool.get('api.token')
        tokens = Token.search([('party', '=', self.id)])
        if tokens:
            token = tokens[0]
            app_url = config.get('web', 'coog_app_url')
            if app_url and token.request_hash:
                return app_url + '/#auth/customer?id=' + token.request_hash
