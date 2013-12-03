from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = [
    'Session',
]

__metaclass__ = PoolMeta


class Session:
    'Session'

    __name__ = 'ir.session'

    @classmethod
    def delete(cls, sessions):
        Log = Pool().get('coop_process.process_log')
        for session in sessions:
            locks = Log.search([
                ('user', '=', session.create_uid),
                ('locked', '=', True)])
            if locks:
                Log.write(locks, {'locked': False})
        super(Session, cls).delete(sessions)

    @classmethod
    def create(cls, values):
        cls.delete(cls.search([('create_uid', '=', Transaction().user)]))
        return super(Session, cls).create(values)
