#!/usr/bin/env python3

"""
When microprobing security fuses half of the chip is dumped at once
Both halves need to be combined into a single usable dump

I dump 2-3 copies of each half into a directory broken into:
-*_lower.jed: lower address space
-*_upper.jed: upper address space

This tool checks the copies for consistency and outputs a single unified .jed
"""

from superpal import jedutil
import glob
import copy

def dedup_jeds(aglob):
    fns = sorted(glob.glob(aglob))
    jeds = []
    print("Checking " + aglob + "...")
    for fn in fns:
        jeds.append(jedutil.load_jed(fn))
    # Verify equivilence
    for fn, jed in zip(fns, jeds):
        print("  " + fn)
        assert jed['data'] == jeds[0]['data']
    return jeds[0]


def combine_jeds(lower, upper):
    ret = copy.deepcopy(lower)
    for addr in range(0, 2048, 32):
        if addr < 2048//2:
            ret['data'][addr] = lower['data'][addr]
        else:
            ret['data'][addr] = upper['data'][addr]
    return ret


def parse_dir(jed_run_dir):
    lower = dedup_jeds("%s/*_lower.jed" % jed_run_dir)
    upper = dedup_jeds("%s/*_upper.jed" % jed_run_dir)
    print("Combining...")
    ret = combine_jeds(lower, upper)
    print("Ready")
    return ret


def run(jed_dir, fn_out):
    jed = parse_dir(jed_dir)
    jedutil.save_jed(jed, fn_out)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('dir', default=None, help='.jed dir')
    parser.add_argument('fn', default=None, help='.jed dir')
    args = parser.parse_args()

    run(args.dir, args.fn)
