from trytond.pool import Pool


def register():
    Pool.register(module='bank_cog_translation', type_='model')
