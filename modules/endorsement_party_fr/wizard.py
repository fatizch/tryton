from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'ChangePartyAddress',
    ]


class ChangePartyAddress:
    __name__ = 'endorsement.party.change_address'

    @classmethod
    def _address_fields_to_extract(cls):
        return super(ChangePartyAddress, cls)._address_fields_to_extract() + \
            ['line3']
