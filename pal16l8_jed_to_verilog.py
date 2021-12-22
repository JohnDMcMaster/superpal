#!/usr/bin/python3

"""
At first I started with a more generic module
Moving instead to generate the module + test harness together
This removes tristates entirely as we just know whether something is an input or output
"""

import subprocess
import re
from collections import OrderedDict

# this info can be parsed from jedutil output

PINS_DUT = None
PINS_DUT_IN = None
PINS_DUT_OUT = None

def pin_n2verilog(pin):
    """pin number to verilog name"""
    pinmap = {}
    inputs = 0
    outputs = 0
    for k, v in PINS_DUT.items():
        if v == "i":
            pinmap[k] = "i[%u]" % inputs
            inputs += 1
        elif v == "o":
            pinmap[k] = "o[%u]" % outputs
            outputs += 1
        else:
            assert 0

    return pinmap[pin]

def gen_top(f):
    def line(l):
        f.write(l + "\n")

    """
    1024 entries
    100 ns per entry
    """
    # sim_time = 102500
    sim_step = 100
    sim_time = ((1 << PINS_DUT_IN) + 1) * sim_step


    line("module pal16l8_sim();")
    line("""
  initial begin
     # %u $finish;
  end

  reg [%u:0] pali = %u'b0;
  wire [%u:0] palo;
  always #%u begin
    pali = pali + %u'b1;
  end

  pal16l8 dut(
    .i(pali),
    .o(palo));
""" % (sim_time, PINS_DUT_IN - 1, PINS_DUT_IN, PINS_DUT_OUT - 1, sim_step, PINS_DUT_OUT))

    line("""
  initial
     $monitor("At time %t, i = %h (%0d), o = %h (%0d)",
              $time, pali, pali, palo, palo);
endmodule
""")

def gen_pal(f, terms):
    def line(l):
        f.write(l + "\n")

    line('module pal16l8(')
    line('        input wire [%u:0] i,' % (PINS_DUT_IN - 1,))
    line('        output wire [%u:0] o' % (PINS_DUT_OUT - 1,))
    line('    );')

    for pinn, func in PINS_DUT.items():
        if func == "o":
            vname = pin_n2verilog(pinn)
            line('    assign %s = %s;' % (vname, terms[vname]))

    line('endmodule')

def write(terms, fn_out):
    f = open(fn_out, "w")

    def line(l):
        f.write(l + "\n")

    line('`default_nettype none')
    line('')

    gen_pal(f, terms)
    line('')
    gen_top(f)


"""
Abandoned
The pin list at the top is just a list of potential options
it doesn't show the actual configuration
Need to scrape the actual logic

Anything not an output is an input?
this also covers outputs being used as equation inputs
"""
def gen_pindefs(outputs):
    global PINS_DUT
    global PINS_DUT_IN
    global PINS_DUT_OUT
    PIN_GND = 10

    """
    # Device speciifc. TODO: auto generate
    PINS_DUT = OrderedDict([
        (1, "i"),
        (2, "i"),
        (3, "i"),
        (4, "i"),
        (5, "i"),
        (6, "i"),
        (7, "i"),
        (8, "i"),
        (9, "i"),
        (11, "i"),
        (12, "o"),
        (13, "o"),
        (14, "o"),
        (15, "o"),
        (16, "o"),
        (17, "o"),
        (18, "o"),
        (19, "o"),
        ])
    """
    PINS_DUT = OrderedDict([])

    # Now order pins
    for pinn in range(1, 20):
        if pinn == PIN_GND:
            continue

        # Input pins 
        if pinn in outputs:
            PINS_DUT[pinn] = "o"
        else:
            PINS_DUT[pinn] = "i"

    PINS_DUT_IN = sum([1 if x == "i" else 0 for x in PINS_DUT.values()])
    PINS_DUT_OUT = sum([1 if x == "o" else 0 for x in PINS_DUT.values()])
    print("Calculated pins: %u input, %u output" % (PINS_DUT_IN, PINS_DUT_OUT))
    assert PINS_DUT_IN
    assert PINS_DUT_OUT

def parse_terms(jedutil_out):
    def pop_line():
        ret = lines[0]
        del lines[0]
        return ret

    def wait_line(s):
        while s not in pop_line():
            pass

    def check_term(x):
        inverted = ''
        if x[0] == '~':
            inverted = '~'
            x = x[1:]
        if x[0] == 'o':
            return inverted + pin_n2verilog(int(x[1:]))
        elif x[0] == 'i':
            return inverted + pin_n2verilog(int(x[1:]))
        else:
            return x

    jedutil_out = jedutil_out.replace("\r\n", "\n")
    for _i in range(40):
        jedutil_out = jedutil_out.replace("\t", " ")
        jedutil_out = jedutil_out.replace("  ", " ")
    jedutil_out = jedutil_out.replace("+\n", "+ ")
    jedutil_out = jedutil_out.replace("  ", " ")
    terms = {}

    lines_orig = jedutil_out.split("\n")

    # pass 1: parse pin definitions
    # collect outputs and assume the rest are inputs
    print('looping for pin defs')
    lines = list(lines_orig)
    outputs = []
    for l in lines:
        l = l.strip()
        m = re.match("/(o.*) = (.*)", l)
        if not m:
            continue
        pinn = int(m.group(1)[1:])
        outputs.append(pinn)
    gen_pindefs(outputs)

    # gen_pindefs(lines)
    print('looping for logic defs')
    lines = list(lines_orig)
    for l in lines:
        l = l.strip()
        m = re.match("/(o.*) = (.*)", l)
        if not m:
            continue
        # print('checking: ', l)
        output = pin_n2verilog(int(m.group(1)[1:]))
        rhs = m.group(2)
        rhs = rhs.replace("/", "~")
        rhs = rhs.replace("+", "|")
        # FIXME: this can probably be simplified now that I'm conforming to their names
        rhs = ' '.join([check_term(x) for x in rhs.split(' ')])
        terms[output] = '~(%s)' % rhs
    return terms

def run(jed_fn_in, v_fn_out):
    raw = subprocess.check_output("jedutil -view %s PAL16L8" % jed_fn_in, shell=True, encoding="ascii")
    terms = parse_terms(raw)
    write(terms, v_fn_out)

def main():
    import argparse

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('jed_in')
    parser.add_argument('v_out')
    args = parser.parse_args()

    run(args.jed_in, args.v_out)

if __name__ == "__main__":
    main()
