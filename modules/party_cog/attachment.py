# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = [
    'Attachment',
    ]


class Attachment:
    __metaclass__ = PoolMeta
    __name__ = 'ir.attachment'

    @classmethod
    def __setup__(cls):
        super(Attachment, cls).__setup__()
        cls._error_messages.update({
                'interaction_attachment': 'Some attachments are used on '
                'interactions with the following parties:\n\n%(parties)s\n\n'
                'Going on will break the links.',
                })

    @classmethod
    def delete(cls, attachments):
        Interaction = Pool().get('party.interaction')
        interactions = Interaction.search(
            [('attachment', 'in', [x.id for x in attachments])])
        if interactions:
            cls.raise_user_warning('interaction_attachment_%s' %
                ''.join(str(x.id) for x in interactions[:10]),
                'interaction_attachment', {
                    'parties': '\n'.join(x.party.rec_name
                        for x in interactions)})
            Interaction.write(interactions, {'attachment': None})
        super(Attachment, cls).delete(attachments)
