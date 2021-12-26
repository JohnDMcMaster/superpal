"""
Something loosely resembling a sim but needs tuning

Which edge?
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

    def verilog_write_top(self, f):
        def line(l):
            f.write(l + "\n")

        """
        1024 entries
        100 ns per entry
        """
        # sim_time = 102500
        sim_step = 100
        # clk step + addr step
        sim_time = ((1 << self.get_npins_in()) + 1) * 2 * sim_step

        line("module sim_top();")
        line("""
  initial begin
     # %u $finish;
  end
""" % sim_time)

        line("""
  reg clk = 1'b0;
  reg [%u:0] pali = %u'b0;
  wire [%u:0] palo;
  always #%u begin
    pali = pali + %u'b1;
  end

""" % (self.get_npins_in() - 1, self.get_npins_in(), self.get_npins_out() - 1,
        2 * sim_step, self.get_npins_out()))

        line("""
  always #%u begin
    clk = ~clk;
  end

  dut dut(
    .i(pali),
    .o(palo));
""" % (sim_time, ))

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

    def verilog_write_pal(self, f, terms):
        def line(l):
            f.write(l + "\n")

        line('module dut(')
        line('        input wire clk,')
        line('        input wire [%u:0] i,' % (self.get_npins_in() - 1, ))
        line('        output wire [%u:0] o' % (self.get_npins_out() - 1, ))
        line('    );')

        def rname(pinn):
            return self.pin_n2verilog(pinn).replace("o", "oreg").replace(
                '[', '').replace(']', '')

        # Register definitions
        for pinn, func in self.PINS_DUT.items():
            if func == "o":
                line("    reg %s = 1'b0;" % (rname(pinn), ))

        line("")

        # Assign output wires to internal regs
        for pinn, func in self.PINS_DUT.items():
            if func == "o":
                line('    assign %s = %s;' %
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

    def verilog_write(self, terms, fn_out):
        f = open(fn_out, "w")

        def line(l):
            f.write(l + "\n")

        line('`default_nettype none')
        line('')

        self.verilog_write_pal(f, terms)
        line('')
        self.verilog_write_top(f)
