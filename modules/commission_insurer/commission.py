# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.config import config
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'Agent',
    ]


class Agent(metaclass=PoolMeta):
    __name__ = 'commission.agent'

    insurer = fields.Many2One('insurer', 'Insurer', ondelete='RESTRICT',
        states={
            'invisible': ~Eval('is_for_insurer'),
            'required': Bool(Eval('is_for_insurer')),
            }, domain=[('party', '=', Eval('party'))],
        depends=['is_for_insurer', 'party'])
    is_for_insurer = fields.Function(
        fields.Boolean('For insurer'), 'on_change_with_is_for_insurer')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        handler = TableHandler(cls, module_name)
        to_migrate = not handler.column_exist('insurer') and \
            config.getboolean('env', 'testing') is not True

        super(Agent, cls).__register__(module_name)

        # Migration from 1.10 : Store insurer
        if to_migrate:
            pool = Pool()
            to_update = cls.__table__()
            insurer = pool.get('insurer').__table__()
            party = pool.get('party.party').__table__()
            update_data = party.join(insurer, condition=(
                    insurer.party == party.id)
                ).select(insurer.id.as_('insurer_id'), party.id)
            cursor.execute(*to_update.update(
                    columns=[to_update.insurer],
                    values=[update_data.insurer_id],
                    from_=[update_data],
                    where=update_data.id == to_update.party))

    @fields.depends('party')
    def on_change_with_is_for_insurer(self, name=None):
        return self.party.is_insurer if self.party else False
