from trytond.pool import Pool


def register():
    Pool.register(module='account_cog_translation', type_='model')
