from trytond.pool import Pool


def register():
    Pool.register(
        module='cog_translation', type_='model')
