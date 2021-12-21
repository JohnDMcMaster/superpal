#!/usr/bin/env bash

set -ex

rm -f pal16r8.jed pal16r8.bin pal16r8.v

cp "$1" pal16r8.jed
jedutil -convert pal16r8.jed pal16r8.bin
./pal16r8_mamebin_to_verilog.py pal16r8.bin >pal16r8.v
./iverilog-go pal16r8_sim.v

