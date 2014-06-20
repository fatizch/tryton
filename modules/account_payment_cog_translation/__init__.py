from trytond.pool import Pool


def register():
    Pool.register(module='account_payment_cog_translation', type_='model')
