#!/usr/bin/python3
"""
At first I started with a more generic module
Moving instead to generate the module + test harness together
This removes tristates entirely as we just know whether something is an input or output
"""

from superpal.verilog.pal16l8 import run


def main():
    import argparse

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--metadata', help="Supplemental parsing data ")
    parser.add_argument('jed_in')
    parser.add_argument('v_out')
    args = parser.parse_args()

    run(args.jed_in, args.v_out, metadata_fn=args.metadata)


if __name__ == "__main__":
    main()
