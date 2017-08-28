# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta


__all__ = [
    'Session',
    ]


class Session:
    __metaclass__ = PoolMeta
    __name__ = 'ir.session'

    @classmethod
    def create(cls, sessions):
        UserConnection = Pool().get('res.user.connection')
        instances = super(Session, cls).create(sessions)
        UserConnection.create([{
                    'key': x.key, 'date': x.create_date.date(),
                    'user_id': x.create_uid.id,
                    'last_activity': x.create_date
                    } for x in instances])
        return instances

    @classmethod
    def write(cls, sessions, parameters):
        super(Session, cls).write(sessions, parameters)
        UserConnection = Pool().get('res.user.connection')
        UserConnection.update_connections(cls._get_connections(sessions))
        return sessions

    @classmethod
    def delete(cls, sessions):
        connections = cls._get_connections(sessions)
        UserConnection = Pool().get('res.user.connection')
        UserConnection.set_end(connections)
        super(Session, cls).delete(sessions)

    @classmethod
    def _get_connections(cls, sessions):
        UserConnection = Pool().get('res.user.connection')
        return UserConnection.search([
            ('key', 'in', [x.key for x in sessions])
            ], order=[('create_date', 'DESC')], limit=1)
