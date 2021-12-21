#!/usr/bin/python3

from superpal.util import add_bool_arg
import shutil
import os
import subprocess

def run(jed_fn_in, readpal_verify=False, opentl866_verify=False, verbose=False):
    tmp_dir = "vtmp"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    os.mkdir(tmp_dir)
    shutil.copy(jed_fn_in, tmp_dir + "/pal16l8.jed")

    cd = "cd %s &&" % (tmp_dir,)

    print("")
    print("")
    print("")
    print("Converting to view")
    subprocess.check_call(cd + "jedutil -view pal16l8.jed PAL16L8 >pal16l8.view", shell=True, encoding="ascii")

    print("")
    print("")
    print("")
    print("Converting to verilog")
    subprocess.check_call(cd + "../pal16l8_jed_to_verilog.py pal16l8.jed pal16l8_sim.v", shell=True, encoding="ascii")

    print("")
    print("")
    print("")
    print("Compiling")
    subprocess.check_call(cd + "iverilog -o pal16l8_sim.iv pal16l8_sim.v", shell=True, encoding="ascii")

    print("")
    print("")
    print("")
    print("Running sim")
    subprocess.check_call(cd + "vvp pal16l8_sim.iv", shell=True, encoding="ascii")

def main():
    import argparse

    parser = argparse.ArgumentParser(description='')
    add_bool_arg(parser, "--verbose")
    parser.add_argument('--readpal-verify', help="Verify using readpal type EPROM capture")
    parser.add_argument('--opentl866-verify', help="Verify using opentl866 type capture")
    parser.add_argument('jed_in')
    args = parser.parse_args()

    run(args.jed_in, readpal_verify=args.readpal_verify, opentl866_verify=args.opentl866_verify, verbose=args.verbose)

if __name__ == "__main__":
    main()
