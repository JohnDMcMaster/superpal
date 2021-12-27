from collections import OrderedDict
import re
import json
import subprocess

from . import vutil

# this info can be parsed from jedutil output


class PAL16L8(vutil.PAL):
    def part(self):
        return "PAL16L8"

    def is_io_pinn(self, pinn):
        return pinn not in (self.PIN_GND, self.PIN_VCC)

    def verilog_write_pal(self, f, terms):
        def line(l):
            f.write(l + "\n")

        line('module dut(')
        line('        input wire [%u:0] i,' % (self.get_npins_in() - 1, ))
        line('        output wire [%u:0] o' % (self.get_npins_out() - 1, ))
        line('    );')

        for pinn, func in self.PINS_DUT.items():
            if func == "o":
                vname = self.pin_n2verilog(pinn)
                line('    assign %s = %s;' % (vname, terms[vname]))

        line('endmodule')

    def create_sim_mask(self):
        """
        Current simulation has issues with anything touching latches
        Latches occur when a term depends on itself
        Recursively find all terms that have latch dependencies:
        -They themselves are a latch
        -They depend on another term that is a latch
        """

        # By package pin number
        self.looped = {}
        for (lhs_net, equation) in self.view.equations.items():
            _lhs_isinv, (lhs_bus, lhs_pinn), _oper, rhs_terms = equation
            self.looped[lhs_pinn] = False

        new_loop = True
        while new_loop:
            new_loop = False
            for (lhs_net, equation) in self.view.equations.items():
                _lhs_isinv, (lhs_bus, lhs_pinn), _oper, rhs_terms = equation
                if self.looped[lhs_pinn]:
                    continue

                for termi, term in enumerate(rhs_terms):
                    # Skip operators
                    if termi % 2 == 1:
                        continue
                    rhs_net, _lhs_isinv, _rhs_buspinn = term
                    if lhs_net == rhs_net:
                        self.looped[lhs_pinn] = True
                        new_loop = True
                        break

    def verilog_write_top(self, f):
        def line(l):
            f.write(l + "\n")

        """
        1024 entries
        100 ns per entry
        """
        # sim_time = 102500
        sim_step = 100
        sim_time = ((1 << self.get_npins_in()) + 1) * sim_step

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
""" % (sim_time, self.get_npins_in() - 1, self.get_npins_in(),
        self.get_npins_out() - 1, sim_step, self.get_npins_out()))

        ifmt = "%h" * self.get_npins_in()
        ofmt = "%h" * self.get_npins_out()
        iargs = ", ".join("pali[%u]" % (self.get_npins_in() - i - 1)
                          for i in range(self.get_npins_in()))
        oargs = ", ".join("palo[%u]" % (self.get_npins_out() - i - 1)
                          for i in range(self.get_npins_out()))

        line("""
  initial
     $monitor("t=%t, i=""" + ifmt + """, o=""" + ofmt + """",
              $time,
              """ + iargs + """,
              """ + oargs + """);
endmodule
""")

    def verilog_write(self, terms, fn_out):
        f = open(fn_out, "w")

        def line(l):
            f.write(l + "\n")

        line('`default_nettype none')
        line('')

        self.verilog_write_pal(f, terms)
        line('')
        self.verilog_write_top(f)
