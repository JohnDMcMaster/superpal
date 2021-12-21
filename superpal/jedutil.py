#!/usr/bin/env python3
from collections import OrderedDict
import re
import glob
from PIL import Image
import os
import shutil
import math

nbits = None
imw = None
imh = None
imbits = None

def load_jed(fn):
    """
    JEDEC file generated by 1410/84 from PALCE20V8H-15 06/28/20 22:42:11*
    DM AMD*
    DD PALCE20V8H-15*
    QF2706*
    G0*
    F0*
    L00000 0000000000000000000000000100000000000000*
    """
    ret = {}
    d = OrderedDict()
    with open(fn) as f:
        for l in f:
            # remove *, newline
            l = l.strip()[0:-1]
            if not l:
                continue
            parts = l.split(" ")
            if parts[0] == "DM":
                ret["vendor"] = parts[1]
            elif parts[0] == "DD":
                ret["part"] = parts[1]
            elif l[0:2] == "QF":
                ret["len"] = int(l[2:])
            elif l[0] == "L":
                # L00000 0000000000000000000000000100000000000000*
                addr, bits = l.split(" ")
                addr = int(addr[1:], 10)
                d[addr] = bits
            else:
                continue

    ret["data"] = d
    return ret

def jed2txt(jed):
    ret = ""
    for v in jed["data"].values():
        ret += v
    assert jed["len"] == nbits
    assert nbits == len(ret), (nbits, len(ret))
    return ret

def load_jed_flat(fn):
    jed = load_jed(fn)
    return jed2txt(jed)

def save_jed(jed, fn_out):
    f = open(fn_out, "w")
    def writeline(s):
        f.write(s + "\r\n")
    writeline("\x02")
    writeline("JEDEC file generated by icfuzz*")
    writeline("DM National Semiconductor*")
    writeline("DD PAL16L8*")
    writeline("QF2048*")
    writeline("G0*")
    writeline("F0*")

    for addr, vals in jed['data'].items():
        writeline("L%05u %s*" % (addr, vals))

    checksum = 0
    writeline("C%04X*" % checksum)
    checksum = 0
    f.write("%04X" % checksum)