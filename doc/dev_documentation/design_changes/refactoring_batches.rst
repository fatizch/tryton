Batch refactoring
=================

Description
-----------

Refactoring goals :

- *G1:* generate complete human-friendy log files as resources to use to
  diagnostic past batches executions
- *G2:* provides a flexible way to configure batches outputs locations/
  filenames
- *G3:* make the batches fault tolerant, ie a batch should not be interrupted
  by an error on a custom object instance when processing many of them
- *G4:* makes batch processing easily scriptable (using a job scheduling tool)
  by returning a meaningful exit status value

Design
------

The overall design has been kept the same : we have two celery tasks
``generate_all`` and ``generate``, the former (the *master task*) takes a
batch name in argument and calls functions on the batch class to split the
job into ``generate`` tasks.

Batches are runned using the ``coop batch`` command and require celery
workers to run in the background.

Batch configuration
^^^^^^^^^^^^^^^^^^^

Rather than relying on getter methods on the batches classes to get its
settings, these settings are now retrievable via a configuration file. This
file is specified in *trytond.conf* under a new *batch* section ::

    [batch]
    config_file = my/path/batch.conf

This batch configuration file has a *default* section that contains settings
common to all batches that were previously implemented as getter functions in
the root ``Batch`` class.
A ``get_conf_items`` method has been written to access a settings, it performs
lookouts in the following order :

- if setting specified in batch own section in configuration file, returns it
- else if setting present in *default* section returns it
- else returns the default value declared in batch class
  ``default_config_items`` dict

Batch output configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^

Alongside ``split_mode`` and ``split_size`` that already existed, new settings
have been created as batches default settings to enable user to control how
files must be named if batch generate output files : ``root_dir``,
``filepath_template`` and  ``filepath_timestamp_format``, see descriptions at
`Configuration batches`_

Batch writing should always be done using ``write_batch_output`` method, that
generates a unique filename from a base filename given as argument and the
above-described settings.



Batch logging
^^^^^^^^^^^^^

Batches loggers have a dual output :

- each log has its own log file named after the batch ``__name__`` located in
  *log_dir* directory (see `Configuration du serveur`_)
- a global log file updated by all batches isntances is located in
  */var/log/celeryd/* with the name of the ``CELERYD_NODES``
  (see `Configuration celery et celeryd`_)

Exceptions are logged at the top level in the ``generate`` task with the
``Logger.exception`` method so that all details are logged.
Batches do log infos (at *info* level) that helps track batch execution ; the
method ``get_print_infos`` can be used to print digests of lists (as batches
mainly deal with lists) without worrying of the list size.

Ultimately, a batch execution ends with one of:

- ``logger.success`` call that prints a message with a *[SUCCESS]* prefix
- or ``logger.failure`` call that prints a message with a *[FAILURE]* prefix



BatchRootNoSelect
^^^^^^^^^^^^^^^^^

This class inherits ``BatchRoot`` and helps reduce boilerplate code for
batches that don't query the database by having default implementations for
few methods.

Batches control flow
^^^^^^^^^^^^^^^^^^^^

When an exception is caught in ``generate``, the current task is splitted in
two substasks that are re-evaluated in order to accomplish the most work.

*Note: `split_size` batch setting should be set to `1` if one does not want
authorize this behaviour.*

The `coop batch` command is now a blocking call : all tasks executions are
collected and `0` is returned if they all executed successfully. Otherwise, `1`
is returned.

Configuration
-------------

- the TrytonTask official module is now used and should be installed using

  .. code-block:: sh

        pip install --no-deps celery-tryton

- trytond.conf : added batch section, see `Configuration du serveur`_
- batch conf file, see `Configuration batches`_
- options specific to each batch, see `Batches`_

.. _Batches: https://doc.coopengo.com/trytond_doc/doc/fr/batches.html
.. _Configuration batches: https://doc.coopengo.com/trytond_doc/doc/fr/administration_configuration/configuration_batch.html
.. _Configuration du serveur: https://doc.coopengo.com/trytond_doc/doc/fr/administration_configuration/configuration_serveur.html#batch
.. _Configuration celery et celeryd: https://doc.coopengo.com/trytond_doc/doc/fr/administration_configuration/configuration_celery.html

Risks
-----

- Bad performances : Medium risk. Naive solution consisting in dividing jobs
  list into two sublists whenever an exception occurs may not be sustainable
  in the long run as it could increase execution time substancially.
  Batch logs will be analyzed to estimate the time penalty and determine if
  it's necessary to implement more advanced control flow.
