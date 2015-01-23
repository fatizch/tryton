Generate mails with many documents merged in a single pdf
=========================================================

Description
-----------

- **Input :** “Impression du courrier” wizard with multiple letters models
  selected on first screen
- **Output :** a pdf that is the concatenation of all odt contents is attached
  in the mail and eventually added to internal edm

Design
------

On wizard first screen, the view now enables user to select multiples models.
If multiple letter models selected, the default name given to output pdf is
the contract number (user can edit it).

Models can be edited before print by user if coog is correctly configured (see
Configuration) or accessible only for previewing in read only mode.
Each odt is individually converted to pdf (using ``unoconv`` as before) and
then they get merged using gs command.

If at least one of the source model has the *Use Internal EDM* set to true, the
resulting pdf is added to the internal EDM.

Configuration
-------------

``gs`` must be installed server side with

.. code-block:: sh

    apt-get install ghostscript

In *trytond.cfg* set ``server_shared_folder`` to a folder on server with write
access.

If user must be able to edit the letter templates, it’s necessary to set
``client_shared_folder`` to the mounted folder (same folder that server write
into) with write access::

    [EDM]
    server_shared_folder = /mnt/mail_documents
    client_shared_folder = F:\partage-serveur\mail_documents


Risks
-----

None: we delete temporary odt files that we create with shutil.rmtree() which
can be dangerous depending on argument given. This risk is mitigated as each
odt is created in its own temporary folder and these are those folders that
are deleted (as opposed to ``server_shared_folder/*`` for example)
