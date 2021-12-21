`default_nettype none
`include "pal16r8.v"

module verify1();
  reg [7:0] pali = 8'b0;
  wire [7:0] palo;

  initial begin
     # 30000 $finish;
  end

  reg clk = 0;
  always #10 begin
    clk = !clk;
  end

  always #100 begin
    pali = pali + 8'b1;
  end

  pal16r8 pal(.clk(clk), .i(pali), .o(palo));  

  initial
     $monitor("At time %t, pali = %h (%0d), palo = %h (%0d)",
              $time, pali, pali, palo, palo);
endmodule

