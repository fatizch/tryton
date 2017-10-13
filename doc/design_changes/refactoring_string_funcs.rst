String transliterations functions refactoring
=============================================

Description
-----------

Existing set of functions is composed of four functions *remove_accentued_char
, remove_invalid_char, remove_all_but_alphanumeric_and_space and
remove_blank_and_invalid_char*.
Problems are :

- bad names : *remove_accentued_char* contains a typo, it's not clear what
  *remove_invalid_char* does, unnecessary long names, etc
- too complex : large overlap between what functionalities the four functions
  provide

The goal of the refactoring is to have a smallest set of functions with
names that better convey their actions.


Design
------

We replace the four functions by the two following ones :

- ``asciify(text)``: takes unicode data and represent it in ASCII characters
- ``slugify(text, char='_', lower=True)``: generate a slug from unicode
  data. Replace accented characters by non accented ones, replace punctuations
  and whitespaces by underscores, convert to lowercase.


Configuration
-------------

*unidecode* module is now necessary and should be installed using

.. code-block:: sh

      pip install unidecode


Risks
-----

Functions are used widely in all the codebase but mostly in
*on_change_with_code functions* (same use case repeated).
Unit tests have been added, specifically to test *zipcode.py* that is the piece
of code that makes the most use of these string functions.
