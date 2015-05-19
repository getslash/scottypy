.. _examples:

Examples
========

Downloading Slash log files
---------------------------

.. code-block:: python

    from subprocess import check_call
    from scotty import Scotty


    s = Scotty()
    beams = s.get_beams_by_tag("be3523fe-fe19-11e4-9be2-00505699a8d9_0")
    for beam in beams:
        for file in beam.files:
            if file.file_name.endswith("debug.log.gz"):
                check_call(['curl', '--compressed', '-O', file.url])
