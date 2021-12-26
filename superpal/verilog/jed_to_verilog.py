from collections import OrderedDict
import re
import json
import subprocess

from . import vutil
from . import pal16l8
from . import pal16r8
from superpal import jedutil


def jed_fn2cls(jed_fn_in):
    jed = jedutil.load_jed(jed_fn_in)

    if jed["part"].find("PAL16L8") == 0:
        pal = pal16l8.PAL16L8()
    elif jed["part"].find("PAL16R8") == 0:
        pal = pal16r8.PAL16R8()
    else:
        assert 0, jed["part"]
    return pal


def run(jed_fn_in, *args, **kwargs):
    pal = jed_fn2cls(jed_fn_in)
    pal.jed_to_verilog(jed_fn_in, *args, **kwargs)
    return pal
