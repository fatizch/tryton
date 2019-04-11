# -*- coding: utf-8 -*-
import os

# -- General configuration ------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['sphinxprettysearchresults']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
# source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'Coog'
copyright = 'Coopengo'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '2.4'
# The full version, including alpha/beta/rc tags.
release = version

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
language = 'fr'

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
# today = ''
# Else, today_fmt is used as the format for a strftime call.
today_fmt = '%d/%m/%Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', '**/summary.rst', '**/features.rst']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'


# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
import sphinx_rtd_theme
html_theme = "sphinx_rtd_theme"
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
# html_theme = 'default'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']

# Output file base name for HTML help builder.
htmlhelp_basename = 'Coog'


# -- Options for LaTeX output ---------------------------------------------

PREAMBLE = """
\\frenchbsetup{ItemLabels=\\textbullet}
"""
latex_elements = {'classoptions': ',openany,oneside', 'papersize': 'a4paper',
    'babel': '\\usepackage[french]{babel}',
    'preamble': PREAMBLE}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    ('index', 'coog_documentation.tex', 'Coog Documentation',
    'Coopengo', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
latex_logo = os.path.join('_static', 'logo.png')

# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'Coog Documentation', 'Coog Documentation',
     ['Coopengo'], 1)
]

# If true, show URL addresses after external links.
# man_show_urls = False


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    ('index', 'Coog Documentation', 'Coog Documentation',
        'Coopengo', 'Coopengo', 'Coog : insurance ERP',
        'Miscellaneous'),
]

# -- Options for Pdf output -------------------------------------------

pdf_documents = [
    ('index', 'Coog Documentation', 'Coog Documentation', 'Coopengo'),
]
