#!/usr/bin/python3

from superpal.util import add_bool_arg
import pal16l8_jed_to_verilog
from superpal.verilog.vutil import pad_

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


def epromi_to_binstr(x):
    return pad_(format(x, '0%ub' % 18))


def epromo_to_binstr(x):
    return pad_(format(x, '0%ub' % 8))


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
    ret = [None] * len(lines)
    for (input, output, _transition) in lines:
        ret[input] = output
    return ret


def check_sim_vs_electrical(pal,
                            sim,
                            electrical,
                            debug_electrical_bin=None,
                            verbose=False):
    if debug_electrical_bin:
        buff = bytearray(len(electrical))
        for addr, val in enumerate(electrical):
            buff[addr] = val
        open(debug_electrical_bin, "wb").write(buff)

    assert len(sim) == len(electrical), (
        "%u sim entries but %u tocheck entries" % (len(sim), len(electrical)))
    n_entries = len(electrical)
    print("Checking 0x%04X entries" % n_entries)

    # MSB first
    in_bits = pal.PINS_DUT_IN
    out_bits = pal.PINS_DUT_OUT
    assert len(sim[0]) == pal.PINS_DUT_OUT

    # Loopback makes read out unstable
    # Verify as much as possible though
    looped_pins = 0
    data_mask = (1 << pal.PINS_DUT_OUT) - 1
    for pinn, looped in pal.metadata['looped'].items():
        if looped:
            net, index = pal.pin_n2vio(pinn)
            assert net == "o"
            data_mask ^= 1 << index
            looped_pins += 1

    ok = 0
    nok = 0

    print("Out bits: %u" % out_bits)
    for addr in range(len(sim)):
        obits = pal.o_to_binstr(electrical[addr])
        verbose and print("0b_%s:    sim 0b_%s cap 0b_%s mask 0b_%s" %
                          (pal.i_to_binstr(addr), pad_(
                              sim[addr]), obits, pal.o_to_binstr(data_mask)))

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
                    "0b_%s: :( sim 0b_%s cap 0b_%s mask 0b_%s (bit %u: %s vs %s)"
                    % (pal.i_to_binstr(addr), pad_(
                        sim[addr]), obits, pal.o_to_binstr(data_mask), biti,
                       bit_sim, bit_electrical))
                nok += 1
                break
            ok += 1

    print("Summary")
    print("  ok: 0x%04X" % ok)
    print("  nok: 0x%04X" % nok)
    print("  looped pins: %u" % looped_pins)
    print("  data_mask: 0b_%s" % pal.o_to_binstr(data_mask))
    assert nok == 0


def run_verify_pal866(pal, pal866_fn, sim_fn, tmp_dir, verbose=False):
    print("Verifying", pal866_fn)
    sim = parse_sim(sim_fn)
    pal866 = parse_pal866_simple(pal866_fn)
    debug_electrical_bin = os.path.join(tmp_dir, "sim_pal866.bin")
    check_sim_vs_electrical(pal,
                            sim,
                            pal866,
                            debug_electrical_bin=debug_electrical_bin,
                            verbose=verbose)


def print_pinmap(pal):
    print("Pin map:")
    for pinn in pal.PINS_DUT.keys():
        bus, n = pal.pin_n2vio(pinn)
        net = "%s[%u]" % (bus, n)
        print("  P%u => %s" % (pinn, net))


def run_verify_readpal(pal, readpal_fn, sim_fn, tmp_dir, verbose=False):
    """
    http://techno-junk.org/readpal.php
    http://dreamjam.co.uk/emuviews/files/adapter-v2-cap.png
    Pin mapping appears to be what I'd call "intuitive"
    """
    print("Verifying", readpal_fn)
    sim = parse_sim(sim_fn)
    eprom = open(readpal_fn, "rb").read()
    electrical = []
    # All outputs as simple bytes
    if 0 and pal.PINS_DUT_OUT == 8:
        # XXX: verify redundant addresses?
        # in case of latches may not be identical though
        for addr in range(1 << pal.PINS_DUT_IN):
            electrical.append(eprom[addr])
    # Fractional word w/ shared input/output
    # Similarly, grab only a sample word, don't grab all word permutations
    # (the lowest address one)
    else:
        # 256 KB of data
        # 16 address lines
        # 8 bits captured at each
        # should be 64 KB?
        # guess 12 and 19 are toggled as well
        print_pinmap(pal)
        ipins = [x[0] for x in pal.PINS_DUT.items() if x[1] == 'i']
        opins = [x[0] for x in pal.PINS_DUT.items() if x[1] == 'o']
        verbose and print('ipins', ipins)
        verbose and print('opins', opins)

        # Map logical pins to address space
        # LSB first
        ipin_eprom_addr_bits = []
        for addr_bit, (_pinn, io) in enumerate(pal.PINS_DUT.items()):
            if io == 'i':
                ipin_eprom_addr_bits.append(addr_bit)
            else:
                assert io == 'o'
        verbose and print("ipin_eprom_addr_bits", ipin_eprom_addr_bits)

        opin_eprom_data_bits = []
        for data_bit, pinn in enumerate(range(12, 20)):
            io = pal.PINS_DUT[pinn]
            if io == 'o':
                opin_eprom_data_bits.append(data_bit)
        verbose and print("opin_eprom_data_bits", opin_eprom_data_bits)

        # Now extract words using bit mapping
        for logical_addr in range(1 << pal.PINS_DUT_IN):
            # Create address
            eprom_addr = 0
            for logical_addri, eprom_addri in enumerate(ipin_eprom_addr_bits):
                if logical_addr & (1 << logical_addri):
                    eprom_addr |= (1 << eprom_addri)
            # Get raw word
            eprom_word = eprom[eprom_addr]

            # extract bits, we may not be using the whole word
            logical_word = 0
            for logical_biti, eprom_biti in enumerate(opin_eprom_data_bits):
                if eprom_word & (1 << eprom_biti):
                    logical_word |= (1 << logical_biti)

            verbose and print(
                "EPROM  %s : %s  =>  logical  %s : %s" %
                (epromi_to_binstr(eprom_addr), epromo_to_binstr(eprom_word),
                 pal.i_to_binstr(logical_addr), pal.o_to_binstr(logical_word)))
            electrical.append(logical_word)

    debug_electrical_bin = os.path.join(tmp_dir, "sim_readpal.bin")
    check_sim_vs_electrical(pal,
                            sim,
                            electrical,
                            debug_electrical_bin=debug_electrical_bin,
                            verbose=verbose)


def run(jed_fn_in,
        verify_readpal_fn=None,
        verify_pal866_fn=None,
        verbose=False):
    tmp_dir = "vtmp"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    os.mkdir(tmp_dir)
    shutil.copy(jed_fn_in, tmp_dir + "/dut.jed")
    root_dir = os.path.dirname(os.path.abspath(__file__))

    cd = "cd %s &&" % (tmp_dir, )

    print("Converting to view")
    subprocess.check_output(cd + "jedutil -view dut.jed PAL16L8 >dut.view",
                            shell=True,
                            encoding="ascii")

    print("Converting to verilog")
    # subprocess.check_output(cd + root_dir + "/pal16l8_jed_to_verilog.py dut.jed sim_top.v", shell=True, encoding="ascii")
    pal = pal16l8_jed_to_verilog.run(tmp_dir + "/dut.jed",
                                     tmp_dir + "/sim_top.v")

    print("Compiling sim")
    subprocess.check_output(cd + "iverilog -o sim_top.iv sim_top.v",
                            shell=True,
                            encoding="ascii")

    print("Running sim")
    sim_out = subprocess.check_output(cd + "vvp sim_top.iv",
                                      shell=True,
                                      encoding="ascii")
    sim_log_fn = tmp_dir + "/sim_top.txt"
    open(sim_log_fn, "w").write(sim_out)

    if verify_pal866_fn:
        print("")
        run_verify_pal866(pal,
                          verify_pal866_fn,
                          sim_log_fn,
                          tmp_dir,
                          verbose=verbose)

    if verify_readpal_fn:
        print("")
        run_verify_readpal(pal,
                           verify_readpal_fn,
                           sim_log_fn,
                           tmp_dir=tmp_dir,
                           verbose=verbose)

    print("")
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
        verify_readpal_fn=args.verify_readpal,
        verify_pal866_fn=args.verify_pal866,
        verbose=args.verbose)


if __name__ == "__main__":
    main()
