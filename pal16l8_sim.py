#!/usr/bin/python3

from superpal.util import add_bool_arg
import pal16l8_jed_to_verilog

import shutil
import os
import subprocess
import json
"""
TODO:
-verilog sim needs to run entire sim length
-pal866_verify
-readpal_verify
    where is the captured data?

LSB is output first for simplicity
"""


def parse_sim(fn):
    """
    t=                   0, i=0000000000, o=1x101111
    t=                 100, i=1000000000, o=1x101111
    t=                 200, i=0100000000, o=1x101111
    """
    ret = {}
    for l in open(fn, "r"):
        try:
            l = l.strip()
            if "t=" not in l:
                continue
            # i = 002 (2), o = 90 (144)
            parts = l.split(",")
            input = int(parts[1].split("=")[1], 2)
            # output = int(parts[0].split("=")[1], 2)
            output = parts[2].split("=")[1]
            ret[input] = output
        except:
            print("FAILED: ", l)
            raise
    assert len(ret) > 0, "Failed to parse sim"
    return ret


def parse_pal866_raw(fn):
    """
    {"part": "PAL16L8", "pins": {"A": [1, 2, 3, 4, 5, 6, 7, 8, 9, 11], "CLK": null, "D": [12, 13, 14, 15, 16, 17, 18, 19], "GND": 10, "OEn": null, "VCC": 20}, "data_words": 1024}
    [0, 128, null]
    [1, 136, null]
    [2, 144, null]
    """
    f = open(fn, "r")
    header = json.loads(f.readline())
    lines = []
    for l in f:
        lines.append(json.loads(l))
    return header, lines


def parse_pal866_simple(fn):
    header, lines = parse_pal866_raw(fn)
    assert header["part"] == "PAL16L8"
    ret = {}
    for (input, output, _transition) in lines:
        ret[input] = output
    return ret


def check_sim_vs_electrical(sim, electrical, pin_metadata):
    assert len(sim) == len(electrical), (
        "%u sim entries but %u tocheck entries" % (len(sim), len(electrical)))

    # Loopback makes read out unstable
    # Verify as much as possible though
    looped_pins = 0
    data_mask = (1 << pal16l8_jed_to_verilog.PINS_DUT_OUT) - 1
    for pinn, looped in pin_metadata['looped'].items():
        if looped:
            net, index = pal16l8_jed_to_verilog.pin_n2vio(pinn)
            assert net == "o"
            data_mask ^= 1 << index
            looped_pins += 1

    ok = 0
    nok = 0
    # MSB first
    out_bits = len(sim[0])

    def o_to_binstr(x):
        return format(x, '0%ub' % out_bits)

    print("Out bits: %u" % out_bits)
    for addr in range(len(sim)):
        obits = o_to_binstr(electrical[addr])
        for biti in range(out_bits):
            # Skip this bit?
            if not ((1 << biti) & data_mask):
                continue
            # MSB is first
            bit_sim = sim[addr][out_bits - biti - 1]
            if bit_sim == 'x':
                continue
            bit_sim = int(bit_sim)
            bit_electrical = (electrical[addr] >> biti) & 1
            if bit_sim != bit_electrical:
                print(
                    "0x%04X: sim 0b%s cap 0b%s mask 0b%s (bit %u: %s vs %s)" %
                    (addr, sim[addr], obits, o_to_binstr(data_mask), biti,
                     bit_sim, bit_electrical))
                nok += 1
                break
            ok += 1

    print("Summary")
    print("  ok: 0x%04X" % ok)
    print("  nok: 0x%04X" % nok)
    print("  looped pins: %u" % looped_pins)
    print("  data_mask: 0b%s" % o_to_binstr(data_mask))
    assert nok == 0


def run_verify_pal866(pal866_fn, sim_fn, pin_metadata):
    sim = parse_sim(sim_fn)
    pal866 = parse_pal866_simple(pal866_fn)
    check_sim_vs_electrical(sim, pal866, pin_metadata)


def run_verify_readpal(readpal_fn, sim_fn, pin_metadata):
    """
    http://techno-junk.org/readpal.php
    http://dreamjam.co.uk/emuviews/files/adapter-v2-cap.png
    Pin mapping appears to be what I'd call "intuitive"
    """
    assert pal16l8_jed_to_verilog.PINS_DUT_OUT == 8, "FIXME: only implemented trivial case"
    sim = parse_sim(sim_fn)
    eprom = open(readpal_fn, "rb").read()
    electrical = []
    for addr in range(1 << pal16l8_jed_to_verilog.PINS_DUT_IN):
        electrical.append(eprom[addr])
    check_sim_vs_electrical(sim, electrical, pin_metadata)


def run(jed_fn_in, verify_readpal=False, verify_pal866=False, verbose=False):
    tmp_dir = "vtmp"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    os.mkdir(tmp_dir)
    shutil.copy(jed_fn_in, tmp_dir + "/pal16l8.jed")
    root_dir = os.path.dirname(os.path.abspath(__file__))

    cd = "cd %s &&" % (tmp_dir, )

    print("Converting to view")
    subprocess.check_output(cd +
                            "jedutil -view pal16l8.jed PAL16L8 >pal16l8.view",
                            shell=True,
                            encoding="ascii")

    print("Converting to verilog")
    # subprocess.check_output(cd + root_dir + "/pal16l8_jed_to_verilog.py pal16l8.jed pal16l8_sim.v", shell=True, encoding="ascii")
    pin_metadata = pal16l8_jed_to_verilog.run(tmp_dir + "/pal16l8.jed",
                                              tmp_dir + "/pal16l8_sim.v")

    print("Compiling sim")
    subprocess.check_output(cd + "iverilog -o pal16l8_sim.iv pal16l8_sim.v",
                            shell=True,
                            encoding="ascii")

    print("Running sim")
    sim_out = subprocess.check_output(cd + "vvp pal16l8_sim.iv",
                                      shell=True,
                                      encoding="ascii")
    sim_log_fn = tmp_dir + "/pal16l8_sim.txt"
    open(sim_log_fn, "w").write(sim_out)

    if verify_pal866:
        run_verify_pal866(verify_pal866, sim_log_fn, pin_metadata)

    if verify_readpal:
        run_verify_readpal(verify_readpal, sim_log_fn, pin_metadata)

    print("Done")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='')
    add_bool_arg(parser, "--verbose")
    parser.add_argument('--verify-readpal',
                        help="Verify using readpal type EPROM capture")
    parser.add_argument('--verify-pal866',
                        help="Verify using pal866 type capture")
    parser.add_argument('jed_in')
    args = parser.parse_args()

    run(args.jed_in,
        verify_readpal=args.verify_readpal,
        verify_pal866=args.verify_pal866,
        verbose=args.verbose)


if __name__ == "__main__":
    main()
