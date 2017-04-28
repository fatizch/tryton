Tables' creation is generally done through an import from a csv file, or a
  copy / paste. For multi dimensional tables, it is possible to display data as
  a two dimensional table by fixating other dimensions values.

- **Tables creation :** Creating a table is done through two steps:

  - Entry of data defining the table (data type, dimensions number, possible
    values for each dimension...)

  - Entry of the table's content. This can be achieved through:

    - Import / export of *Coog* setting

    - Import of a formatted csv file

    - Copy paste of data

    - Manually, cell by cell (only on small size tables)

- ** Tables display :** A multi dimensional table's content can be hard to
  visualize. ``table`` module allows to display this content in two ways:

    - Simple list:  each line of the list contains each dimension's value,
    and the resulting value.

    - 2D table: classic table display. This view is useful for 2 dimensions
    tables, and can be used in N dimensions tables by fixating the values of
    N - 2 dimensions.

- **Index :** An index being a one dimension table, this module allows to handle
  them properly.
