# superpal
PAL verification and reverse engineering utilities

Goals:
  * Provide a workflow for simulating .jed files against test vectors
    * Supported: readpal, pal866
    * Consider: DuPAL
  * Process readpal test vectors dumps into .jed using open source and easy to use tools
    * Current flow requires several steps including Windows GUI
  * Post process microprobing data into .jed
  * Post process microscope images into .jed

See also: https://proghq.org/wiki/index.php/PAL_Brute_Forcing

## PAL16L8 microprobing workflow

Something like:

Step 1: collect test vectors
* Optionally use readpal to collect test vectors (readpal.bin)
  * Suggest running three times
  * However, if latches or FFs are present may not be consistent
* Optionally use pal866 to collect test vectors  (pal866.jl)
  * Suggest running three times
  * However, if latches or FFs are present may not be consistent

Step 2: extract .jed
* Decap chip
* Microprobe lower address fuse and dump (microprobe_lower.jed)
  * Suggest dumping three times to make sure reliable / the same
* Microprobe higher address fuse and dump (microprobe_upper.jed)
  * Suggest dumping three times to make sure reliable / the same
* Use pal16_combine.py to combine microprobe_lower.jed and microprobe_upper.jed
  * I dumped something as PAL16L8 that should have been PAL16R8, so I added --part to fixup here

Step 3: verify test vectors

```
$ pal16l8_sim.py \
        --verify-pal866 pal866.jl \
        --verify-readpal readpal.bin \
        pal16l8.jed
```

This will convert the .jed into verify and simulate changing inputs.
The simulation is compared to test vectors and it will generate a coverage report
indicating how much was tested and if there were any failures.

Notes:
* Only PAL16L8 currently supported, but PAL16R8 is on the roadmap
* Any outputs with latches are masked out from simulation check
  * They were only a small fraction of outputs I needed to check and I was confident enough .jed was good w/o them
* FFs are not currently supported, but will be with PAL16R8

Sample output:

```
$ pal16l8_sim.py \
         --verify-pal866 pal866/p22.jl \
         --verify-readpal readpal/p22.bin \
         microprobe/p22.jed
Converting to view
Converting to verilog
looping for pin defs
Calculated pins: 10 input, 8 output
looping for logic defs
Compiling sim
Running sim

Verifying pal866/p22.jl
Checking 0x0400 entries
Out bits: 8
Summary
  ok: 0x1800
  nok: 0x0000
  looped pins: 2
  data_mask: 0b_1111_0101

Verifying readpal/p22.bin
Checking 0x0400 entries
Out bits: 8
Summary
  ok: 0x1800
  nok: 0x0000
  looped pins: 2
  data_mask: 0b_1111_0101
Done
```

Although there are only 0x400 entries, the simulation ran 0x1800 steps as latch values settled.
Here's an example of one of the latch loops from vtmp/pal16l8.view (numbered by pin):

```
/o15 = /i5 + /i11 & /o15
```

Which then becomes this in vtmp/pal16l8.v (numbered by data bus):

```
    assign o[3] = ~(~i[4] | ~i[9] & ~o[3]);
```

Which unfortunately can't be checked easily with current test vectors.

## Die image to .jed

WARNING: as of 2021-12-24 this is known to be broken: https://github.com/JohnDMcMaster/superpal/issues/5

Summary:
* Use rompar or other tool to get .txt file of bits
  * Do not include factory test row/col, only main data bits
  * TODO: add more specific orientation info
* txt2jed to get .jed file
  * You'll need zorrom installed
  * This script might eventually move to zorrom
