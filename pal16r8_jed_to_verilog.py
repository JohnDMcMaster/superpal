#!/usr/bin/python3
"""

"""

import subprocess
import re


def write(terms, fn_out):
    f = open(fn_out, "w")

    def line(l):
        f.write(l + "\n")

    line('`default_nettype none')
    line('module pal16r8(')
    line('        input wire clk,')
    line('        input wire [7:0] i, // pin  2 = i[0], pin  9 = i[7]')
    line('        output reg [7:0] o = 0); // pin 19 = o[0], pin 12 = o[7]')
    line('    always @(posedge clk) begin')
    for output in range(8):
        line('        o[%d] <= %s;' % (output, terms[output]))
    line('    end')
    line('endmodule')


def parse_terms(jedutil_out):
    """
    Simplify lines
    If a line ends in a +, its a continuation

    /rf15 := /i2 +
             /i3 +
             /rf12 & /rf18 +
             rf12 & rf18

    line('        input wire [7:0] i, // pin  2 = i[0], pin  9 = i[7]')
    line('        output reg [7:0] o = 0); // pin 19 = o[0], pin 12 = o[7]')

    """
    def rf2o(s):
        assert s[0:2] == "rf", s
        s = s[2:]
        return 19 - int(s)

    jedutil_out = jedutil_out.replace("\r\n", "\n")
    jedutil_out = jedutil_out.replace("+\n         ", "+ ")
    terms = {}
    print('looping')
    for l in jedutil_out.split("\n"):
        print(l)
        m = re.match("/(rf.*) := (.*)", l)
        if not m:
            continue
        output = rf2o(m.group(1))
        rhs = m.group(2)
        for i in range(8):
            rhs = rhs.replace("/", "~")
            rhs = rhs.replace("+", "|")
            rhs = rhs.replace("rf%u" % (19 - i, ), "o[%u]" % i)
            rhs = rhs.replace("i%u" % (i + 2), "i[%u]" % i)
        terms[output] = rhs
    return terms


def run(jed_fn_in, v_fn_out):
    raw = subprocess.check_output("jedutil -view %s PAL16R8" % jed_fn_in,
                                  shell=True,
                                  encoding="ascii")
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
