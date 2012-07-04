from trytond.pool import Pool


def register():
    Pool.register(
        module='insurance_party_fr', type_='model')
