import datetime
from proteus import Model

__all__ = ['create_party_person']


def create_party_person(name=None, first_name=None, birth_date=None):
    "Create default party person"
    Party = Model.get('party.party')

    if not name:
        name = 'Doe'
    if not first_name:
        first_name = 'John'
    if not birth_date:
        birth_date = datetime.date(1980, 10, 14)
    person = Party(
        name=name,
        first_name=first_name,
        is_person=True,
        gender='male',
        birth_date=birth_date)
    person.save()
    return person
