from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='insurance_contract',
      version=version,
      description="Coopengo insurance contract  classes for Tryton",
      long_description="""\
""",
      classifiers=[],
      keywords='tryton coopengo workflow business classes insurance contract',
      author='',
      author_email='',
      url='',
      license='',
      package_dir={'trytond.modules.insurance_contract': '.', },
      packages=['trytond.modules.insurance_contract', ],
      package_data={'trytond.modules.insurance_contract':
                                ['*.py', '*.xml', '*.pyc'], },
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      [trytond.modules]
      insurance_contract = trytond.modules.insurance_contract
      """,
      )
