# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.modules.coog_core import fields, model

__all__ = [
    'Provider',
    ]

PROVIDER_NAMES = [
    ('google', 'Google'),
    ('facebook', 'Facebook'),
    ]


class Provider(model.CoogSQL, model.CoogView):
    'API Providers'
    __name__ = 'api.provider'

    active = fields.Boolean('active')
    user_identifier = fields.Char('User', required=True)
    provider = fields.Selection(PROVIDER_NAMES, 'Provider', required=True)
    token = fields.Many2One('api.token', 'Token',
        required=True, ondelete='CASCADE')

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def create(cls, vlist):
        res = super(Provider, cls).create(vlist)
        pool = Pool()
        Token = pool.get('api.token')
        tokens = [prov['token'] for prov in vlist if prov['token']]
        tokens = Token.browse(tokens)
        Token.write(tokens, {'request_hash': None})
        Token.save(tokens)
        return res
