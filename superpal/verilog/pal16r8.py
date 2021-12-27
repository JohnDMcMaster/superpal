"""
Something loosely resembling a sim but needs tuning

2021-12-26
pal866 captured data has glitches
the first output was a simple clock divider 
but it sometimes glitches
so abandoned for now except for combinatorial only inputs
probably needs pal866 for proper support

Which edge?
    think ffs trigger on falling
eprom lsb is clk pin
pin 11 becomes oen

mask sim results when OE triggered
"""

from collections import OrderedDict
import re
import json
import subprocess

from . import vutil


class PAL16R8(vutil.PAL):
    def __init__(self, *args, **kwargs):
        self.PIN_CLK = 1
        self.PIN_OEn = 11
        vutil.PAL.__init__(self, *args, **kwargs)

    def part(self):
        return "PAL16R8"

    def is_io_pinn(self, pinn):
        return pinn not in (self.PIN_GND, self.PIN_VCC, self.PIN_CLK,
                            self.PIN_OEn)

    def create_sim_mask(self):
        """
        Register setup is not reliable
        So only keep things that depend on inputs, not regs
        """

        # By package pin number
        self.looped = {}
        for (lhs_net, equation) in self.view.equations.items():
            _lhs_isinv, (lhs_bus, lhs_pinn), _oper, rhs_terms = equation
            self.looped[lhs_pinn] = False

        for (lhs_net, equation) in self.view.equations.items():
            _lhs_isinv, (lhs_bus, lhs_pinn), _oper, rhs_terms = equation

            for termi, term in enumerate(rhs_terms):
                # Skip operators
                if termi % 2 == 1:
                    continue
                rhs_net, _lhs_isinv, _rhs_buspinn = term
                if "i" not in rhs_net:
                    self.looped[lhs_pinn] = True
                    break

    def verilog_write_pal(self, f, terms):
        def line(l):
            f.write(l + "\n")

        line('module dut(')
        line('        input wire clk,')
        line('        input wire oen,')
        line('        input wire [%u:0] i,' % (self.get_npins_in() - 1, ))
        line('        output wire [%u:0] o' % (self.get_npins_out() - 1, ))
        line('    );')

        def rname(pinn):
            return self.pin_n2verilog(pinn).replace("o", "oreg").replace(
                '[', '').replace(']', '')

        # Register definitions
        for pinn, func in self.PINS_DUT.items():
            if func == "o":
                line("    reg %s = 1'b1;" % (rname(pinn), ))

        line("")

        # Assign output wires to internal regs
        for pinn, func in self.PINS_DUT.items():
            if func == "o":
                line("    assign %s = oen ? 1'bz : %s;" %
                     (self.pin_n2verilog(pinn), rname(pinn)))

        line("")

        # Main logic
        line('    always @(posedge clk) begin')
        for pinn, func in self.PINS_DUT.items():
            if func == "o":
                line('        %s <= %s;' %
                     (rname(pinn), terms[self.pin_n2verilog(pinn)]))
        line('    end')

        line('endmodule')

    def verilog_write_top(self, f):
        def line(l):
            f.write(l + "\n")

        # CLK, OEn
        nepromi = self.get_npins_in() + 2
        """
        1024 entries
        100 ns per entry
        """
        # sim_time = 102500
        sim_step = 100
        # clk step + addr step
        sim_time = ((1 << nepromi) + 1) * sim_step

        line("module sim_top();")
        line("""
  initial begin
      $dumpfile("dut.vcd");
     $dumpvars(0, sim_top);
  end

  initial begin
     # %u $finish;
  end
""" % sim_time)

        # readpal: EPROM LSB is CLK
        line("    reg [%u:0] epromi = %u'b0;" % (nepromi - 1, nepromi))
        line("    wire clk = epromi[0];")
        line("    wire oen = epromi[9];")
        # Skip CLK, OEn
        line("    wire [%u:0] pali = {epromi[8:1]};" %
             (self.get_npins_in() - 1, ))
        line("    wire [%u:0] palo;" % (self.get_npins_out() - 1, ))

        line("""
  always #%u begin
    epromi = epromi + %u'b1;
  end
""" % (sim_step, nepromi))
        '''
        line("""
  always #%u begin
    clk = ~clk;
  end""" % (sim_step, ))
      '''

        line("""
  dut dut(
    .clk(clk),
    .oen(oen),
    .i(pali),
    .o(palo));
""")

        ifmt = "%b" * nepromi
        ofmt = "%b" * self.get_npins_out()
        iargs = ", ".join("epromi[%u]" % (nepromi - i - 1)
                          for i in range(nepromi))
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
