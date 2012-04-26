from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='insurance_process',
      version=version,
      description="Coopengo insurance process classes for Tryton",
      long_description="""\
""",
      classifiers=[],
      keywords='tryton coopengo workflow business classes insurance process',
      author='',
      author_email='',
      url='',
      license='',
      package_dir={'trytond.modules.insurance_process': '.', },
      packages=['trytond.modules.insurance_process', ],
      package_data={'trytond.modules.insurance_process':
                                ['*.py', '*.xml', '*.pyc'], },
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      [trytond.modules]
      insurance_process = trytond.modules.insurance_process
      """,
      )
