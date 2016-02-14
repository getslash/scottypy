.. _examples:

Examples
========

Downloading Slash log files
---------------------------

.. code-block:: python

    from subprocess import check_call
    from scottypy import Scotty


    s = Scotty("http://somescotty.somedomain.com")
    beams = s.get_beams_by_tag("be3523fe-fe19-11e4-9be2-00505699a8d9_0")
    for beam in beams:
        for file in beam.iter_files():
            if file.file_name.endswith("debug.log.gz"):
                file.download()
