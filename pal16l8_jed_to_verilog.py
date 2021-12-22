#!/usr/bin/python3

"""
At first I started with a more generic module
Moving instead to generate the module + test harness together
This removes tristates entirely as we just know whether something is an input or output
"""

import subprocess
import re
from collections import OrderedDict
import json

# this info can be parsed from jedutil output

PINS_DUT = None
PINS_DUT_IN = None
PINS_DUT_OUT = None

def mk_pinmap():
    pinmap = {}
    inputs = 0
    outputs = 0
    for k, v in PINS_DUT.items():
        if v == "i":
            pinmap[k] = ("i", inputs)
            inputs += 1
        elif v == "o":
            pinmap[k] = ("o", outputs)
            outputs += 1
        else:
            assert 0
    return pinmap

def pin_n2verilog(pin):
    """pin number to verilog name"""
    net, index = mk_pinmap()[pin]
    return "%s[%u]" % (net, index)

def pin_n2vio(pin):
    """pin number to verilog io number"""
    return mk_pinmap()[pin]

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

    def parse_term(x):
        inverted = ''
        if x[0] == '~':
            inverted = '~'
            x = x[1:]
        if x[0] == 'i' or x[0] == 'o':
            pinn = int(x[1:])
            return pinn, inverted
        else:
            return None

    jedutil_out = jedutil_out.replace("\r\n", "\n")
    for _i in range(40):
        jedutil_out = jedutil_out.replace("\t", " ")
        jedutil_out = jedutil_out.replace("  ", " ")
    jedutil_out = jedutil_out.replace("+\n", "+ ")
    jedutil_out = jedutil_out.replace("  ", " ")
    terms = {}
    # By package pin number
    metadata = {
        'looped': {},
        "pins_dut": PINS_DUT,
        "pins_dut_in": PINS_DUT_IN,
        "pins_dut_out": PINS_DUT_OUT,
        }

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
        l_pinn = int(m.group(1)[1:])
        output = pin_n2verilog(l_pinn)
        rhs = m.group(2)

        rhs = rhs.replace("/", "~")
        rhs = rhs.replace("+", "|")

        def is_term_looped(x):
            res = parse_term(x)
            if res:
                pinn, _inverted = res
                # Looped if its equation contains itself
                return pinn == l_pinn
            else:
                return False
        is_looped = bool(sum([is_term_looped(x) for x in rhs.split(' ')]))
        metadata['looped'][l_pinn] = is_looped

        def munge_term(x):
            res = parse_term(x)
            if res:
                pinn, inverted = res
                return inverted + pin_n2verilog(pinn)
            else:
                return x
    
        rhs = ' '.join([munge_term(x) for x in rhs.split(' ')])


        terms[output] = '~(%s)' % rhs
    return terms, metadata

def run(jed_fn_in, v_fn_out, metadata_fn=None):
    raw = subprocess.check_output("jedutil -view %s PAL16L8" % jed_fn_in, shell=True, encoding="ascii")
    terms, metadata = parse_terms(raw)
    write(terms, v_fn_out)
    if metadata_fn:
        open(metadata_fn, "w").write(json.dumps(metadata, sort_keys=True, indent=4, separators=(',', ': ')))
    return metadata

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