from trytond.pool import Pool


def register():
    Pool.register(module='company_cog_translation', type_='model')
