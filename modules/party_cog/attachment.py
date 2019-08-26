# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.exceptions import UserWarning
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool

__all__ = [
    'Attachment',
    ]


class Attachment(metaclass=PoolMeta):
    __name__ = 'ir.attachment'

    @classmethod
    def delete(cls, attachments):
        pool = Pool()
        Interaction = pool.get('party.interaction')
        Warning = pool.get('res.user.warning')
        interactions = Interaction.search(
            [('attachment', 'in', [x.id for x in attachments])])
        if interactions:
            key = ('interaction_attachment_%s' %
                ''.join(str(x.id) for x in interactions[:10]))
            if Warning.check(key):
                raise UserWarning(
                    key,
                    gettext('party_cog.msg_interaction_attachment',
                        parties='\n'.join(
                            x.party.rec_name for x in interactions),
                        ))
            Interaction.write(interactions, {'attachment': None})
        super(Attachment, cls).delete(attachments)
