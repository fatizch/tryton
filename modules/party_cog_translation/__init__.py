from trytond.pool import Pool


def register():
    Pool.register(module='party_cog_translation', type_='model')
