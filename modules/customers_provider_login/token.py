# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import uuid

from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.rpc import RPC
from trytond.config import config

__all__ = [
    'Token',
    ]


class Token:
    __metaclass__ = PoolMeta
    __name__ = 'api.token'

    request_hash = fields.Char('Request Hash', help='Allow user to create'
            ' Token via Api')

    @classmethod
    def __setup__(cls):
        super(Token, cls).__setup__()
        cls.__rpc__.update({'verify_request_hash': RPC(unique=False)})

    @classmethod
    def verify_request_hash(cls, hash_value):
        tokens = cls.search([('request_hash', '=', hash_value)])
        if tokens:
            return tokens[0].id

    @classmethod
    def create_request_hash(cls, parties):
        web_user = config.getint('web', 'web_user')
        if not web_user:
            return
        tokens = cls.search([
            ('active', '=', True),
            ('party', 'in', parties)
            ])
        parties = {x for x in parties if x not in [t.party for t in tokens]}
        tokens = cls.create([{
            'party': p, 'request_hash': uuid.uuid4().hex,
            'user': web_user, 'name': p.name}
            for p in parties])
