#!/usr/bin/env bash

set -ex

rm -rf vtmp
rm -f pal16l8.jed pal16l8.bin pal16l8.v
rm -f pal16r8.jed pal16r8.bin pal16r8.v

mkdir vtmp
cp "$1" vtmp/pal16l8.jed
pushd vtmp

echo
echo
echo "Converting to view"
jedutil -view pal16l8.jed PAL16L8 >pal16l8.view

echo
echo
echo "Converting to verilog"
../pal16l8_jed_to_verilog.py pal16l8.jed pal16l8_sim.v

echo
echo
echo "Compiling"
iverilog -o pal16l8_sim.iv pal16l8_sim.v

echo
echo
echo "Running"
vvp pal16l8_sim.iv

