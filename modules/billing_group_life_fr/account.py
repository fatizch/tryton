from trytond.pool import PoolMeta

from trytond.modules.cog_utils import coop_string


__metaclass__ = PoolMeta
__all__ = [
    'Move',
    'MoveLine',
    ]


class Move:
    __name__ = 'account.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls.coverage_details.domain[1].append(
            ('second_origin', 'like', 'billing.premium_rate.form,%'))


class MoveLine:
    __name__ = 'account.move.line'

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._error_messages.update({
                'mes_rate_note_compensation': 'Rate Note Compensation',
                })

    @classmethod
    def _get_second_origin(cls):
        result = super(MoveLine, cls)._get_second_origin()
        result.append('billing.premium_rate.form')
        return result

    def get_second_origin_name(self, name):
        if not (hasattr(self, 'second_origin') and self.second_origin):
            return ''
        if not self.second_origin.__name__ == 'billing.premium_rate.form':
            return super(MoveLine, self).get_second_origin_name(name)
        return coop_string.translate(self, '', 'mes_rate_note_compensation',
            'error')
