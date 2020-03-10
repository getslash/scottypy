#!/usr/bin/env python
import os


def beam_up(beam_id, path, transporter_addr):
    with open(os.path.join(path, 'output'), 'w') as f:
        f.write("beam_id={beam_id}, path={path}, transporter_addr={transporter_addr}, version=v1".format(
            beam_id=beam_id, path=path, transporter_addr=transporter_addr
        ))

