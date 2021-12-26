from collections import OrderedDict
import re
import json
import subprocess

from . import vutil

# this info can be parsed from jedutil output


class PAL16L8(vutil.PAL):
    def parse_terms(self, jedutil_out):
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
        self.metadata = {
            'looped': {},
            "pins_dut": self.PINS_DUT,
            "pins_dut_in": self.PINS_DUT_IN,
            "pins_dut_out": self.PINS_DUT_OUT,
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
        self.gen_pindefs(outputs)

        # gen_pindefs(lines)
        print('looping for logic defs')
        # propagate potential loops to new definitions on metadata['looped']
        for _loops in range(8):
            lines = list(lines_orig)
            for l in lines:
                l = l.strip()
                m = re.match("/(o.*) = (.*)", l)
                if not m:
                    continue
                # print('checking: ', l)
                l_pinn = int(m.group(1)[1:])
                output = self.pin_n2verilog(l_pinn)
                rhs = m.group(2)

                rhs = rhs.replace("/", "~")
                rhs = rhs.replace("+", "|")

                def is_term_looped(x):
                    res = parse_term(x)
                    if res:
                        pinn, _inverted = res
                        # Looped if its equation contains itself
                        return pinn == l_pinn or self.metadata['looped'].get(
                            l_pinn, False)
                    else:
                        return False

                is_looped = bool(
                    sum([is_term_looped(x) for x in rhs.split(' ')]))
                self.metadata['looped'][l_pinn] = is_looped

                def munge_term(x):
                    res = parse_term(x)
                    if res:
                        pinn, inverted = res
                        return inverted + self.pin_n2verilog(pinn)
                    else:
                        return x

                rhs = ' '.join([munge_term(x) for x in rhs.split(' ')])

                terms[output] = '~(%s)' % rhs
        return terms


def verilog_write_top(pal, f):
    def line(l):
        f.write(l + "\n")

    """
    1024 entries
    100 ns per entry
    """
    # sim_time = 102500
    sim_step = 100
    sim_time = ((1 << pal.PINS_DUT_IN) + 1) * sim_step

    line("module sim_top();")
    line("""
  initial begin
     # %u $finish;
  end

  reg [%u:0] pali = %u'b0;
  wire [%u:0] palo;
  always #%u begin
    pali = pali + %u'b1;
  end

  dut dut(
    .i(pali),
    .o(palo));
""" % (sim_time, pal.PINS_DUT_IN - 1, pal.PINS_DUT_IN, pal.PINS_DUT_OUT - 1,
       sim_step, pal.PINS_DUT_OUT))

    ifmt = "%h" * pal.PINS_DUT_IN
    ofmt = "%h" * pal.PINS_DUT_OUT
    iargs = ", ".join("pali[%u]" % (pal.PINS_DUT_IN - i - 1)
                      for i in range(pal.PINS_DUT_IN))
    oargs = ", ".join("palo[%u]" % (pal.PINS_DUT_OUT - i - 1)
                      for i in range(pal.PINS_DUT_OUT))

    line("""
  initial
     $monitor("t=%t, i=""" + ifmt + """, o=""" + ofmt + """",
              $time,
              """ + iargs + """,
              """ + oargs + """);
endmodule
""")


def verilog_write_pal(pal, f, terms):
    def line(l):
        f.write(l + "\n")

    line('module dut(')
    line('        input wire [%u:0] i,' % (pal.PINS_DUT_IN - 1, ))
    line('        output wire [%u:0] o' % (pal.PINS_DUT_OUT - 1, ))
    line('    );')

    for pinn, func in pal.PINS_DUT.items():
        if func == "o":
            vname = pal.pin_n2verilog(pinn)
            line('    assign %s = %s;' % (vname, terms[vname]))

    line('endmodule')


def verilog_write(pal, terms, fn_out):
    f = open(fn_out, "w")

    def line(l):
        f.write(l + "\n")

    line('`default_nettype none')
    line('')

    verilog_write_pal(pal, f, terms)
    line('')
    verilog_write_top(pal, f)


def run(jed_fn_in, v_fn_out, metadata_fn=None):
    raw = subprocess.check_output("jedutil -view %s PAL16L8" % jed_fn_in,
                                  shell=True,
                                  encoding="ascii")
    pal = PAL16L8()
    terms = pal.parse_terms(raw)
    verilog_write(pal, terms, v_fn_out)
    if metadata_fn:
        open(metadata_fn, "w").write(
            json.dumps(pal.metadata,
                       sort_keys=True,
                       indent=4,
                       separators=(',', ': ')))
    return pal
