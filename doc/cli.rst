CLI reference
=============

scottypy contains a command line tool called ``scotty`` which can be use to invoke Scotty commands from the command line.

Setting the base scotty URL
---------------------------
The first thing you should do when using the command line is set the base URL of Scotty. Because Scotty is an open source on-premise software, there's no "default" site, so one must set the scotty command line tool to use its own Scotty site. This is achieved by the ``set-url`` subcommand. Assuming that your Scotty URL is http://scotty.infinidat.com, you should invoke:

.. code:: bash

   scotty set-url http://scotty.infinidat.com


Downloading Beams (AKA Beaming Down)
------------------------------------

Downloading a beam is achieved using the ``down`` subcommand. Assuming that you want to download beam #1234, you should run:

.. code:: bash

   scotty down 1234

A directory named after the beam ID will be created in your working directory, and the beam will be downloaded to that directory. If you wish to specify your own destination path, use the ``--dest`` flag. This flag is useful for providing user friendly names for the beams:

.. code:: bash

   scotty down 1234 --dest "keyerror_exceptions_logs"

The destination directory will contain, in addition to the beam files, a special file called "beam.txt". This file contains basic information about the beam and it is not part of the original beam files. The purpose of this file is to allow you to see information about the beam without opening your browser.

The down subcommand will not overwrite exiting files. To change this behavior, use the ``--overwrite`` flag. However, this behavior allows you to resume an interrupted beam downloaded, so it should not be used unless you know what you're doing.

If you wish to download only specific files then you should use the ``-f`` or ``--filter`` flag. You should specify case-insensitive string which is a part of the file name. For example:

.. code:: bash

   scotty down -f debug.log 1234

Will download only the files containing "debug.log" in their path from beam #1234. This includes file named "debug.log.gz".

Sometimes one wishes to download a tagged group of beams. This can be achieved by specifying the ``t:`` prefix in the down command. For example

.. code:: bash

   scotty down t:microwave_test_1

This command will create a directory called "microwave_test_1". Inside it, it will create sub-directories named after the beams ids of every beam which is associated which the microwave_test_1 tag. All the flags described above are also valid in this mode.
     

Linking Beams
~~~~~~~~~~~~~

Sometimes beams contain large number of files, or large files, so you may want to wish to inspect them without wasting precious space on your machine. This is achieved by using the ``link`` subcommand instead of ``down``.

Before using this command, the administrator of Scotty should set up a machine which has a mount to Scotty's storage, preferably a read only mount under ``/var/scotty``.

Once this machine has been set up, one can SSH into it and use the ``link`` subcommand just as it would use the ``down`` subcommand. The effect will be the same, but instead of downloading the files from Scotty and wasting previous space, a directory containing symbolic links to the original files will be created. This directory can be safely deleted once the user is done inspecting the beam(s).

.. note:: In order to prevent unfortunate mistakes, it is very important that the administrator setting up the "view" machine will mount Scotty's storage in read-only mode.

Uploading Beams (AKA Beaming Up)
--------------------------------

From Your Computer
~~~~~~~~~~~~~~~~~~

Uploading files from your computer is achieved by the ``up local`` subcommand. For example

.. code:: bash

   scotty up local ~/.slash/logs

Will upload this entire directory to Scotty. The beam number will be displayed at the end of the beam.

From A Remote Computer
~~~~~~~~~~~~~~~~~~~~~~

Ordering Scotty to upload files from a remote computer is achieved by the ``up remote`` subcommand. For example:

.. code:: bash

   scotty up remote bob@machine:/path/to/logs

Will order Scotty to SSH into ``machine`` with the user ``bob`` and upload ``/path/to/logs``. The password will be prompted once the command is run. For security concerns, is it impossible to specify the password as a command line flag. However, it is possible to use the ``--rsa_key`` flag in order to specify the path of an **unencrypted** RSA private key. This private key will be sent to Scotty and it will use it in order to authenticate as ``bob``. This method allows beaming up from bash scripts, as it does not prompt the user for a password.

.. note:: The private key that you specify in ``--rsa_key`` will be sent to Scotty. Never send your own personal key with this method. Instead, you should use SSH keys generated for a specific purpose. It is also required that the specified key will be unencrypted.

The ``--goto`` flag will cause the browser to be opened in the beam page.

When initiating a remote beam, you can use ``--email`` to specify your email. This will cause the beam to be associated with your user.

Once a remote beam has been initiated, the computer that issued the beam doesn't need to be kept open.

Miscellaneous Operations
------------------------

Displaying Information About A Beam
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``show`` subcommand shows information about the given beam or a tag. For example:

.. code:: bash

   scotty show t:3f4eb176-c5b6-11e5-9efc-68f72864767c_0

Tagging A Beam
~~~~~~~~~~~~~~

The ``tag`` subcommand can be used to add or remove tags. To add a tag:

.. code:: bash

   scotty tag some_test_tag 1234

Deletion is done by using the ``-d`` flag

.. code:: bash

   scotty tag -d some_test_tag 1234

Setting A Beam's comment
~~~~~~~~~~~~~~~~~~~~~~~~

``set_command`` is used for setting a beam's comment

.. code:: bash

   scotty set_comment 443346 "Logs of microwave testing #5"
