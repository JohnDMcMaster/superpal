from collections import OrderedDict


def pad_(s):
    # Starting from right, add _ every 4 chars
    ret = ""
    ri = 0
    for i in range(len(s)):
        i = len(s) - i - 1
        if ri and ri % 4 == 0:
            ret = "_" + ret
        ret = s[i] + ret
        ri += 1
    return ret


class PAL:
    def __init__(self):
        self.PINS_DUT = None
        self.PINS_DUT_IN = None
        self.PINS_DUT_OUT = None
        self.metadata = None

    def i_to_binstr(self, x):
        return pad_(format(x, '0%ub' % self.PINS_DUT_IN))

    def o_to_binstr(self, x):
        return pad_(format(x, '0%ub' % self.PINS_DUT_OUT))

    def gen_pindefs(self, outputs):
        self.PIN_GND = 10
        self.PINS_DUT = OrderedDict([])

        # Now order pins
        for pinn in range(1, 20):
            if pinn == self.PIN_GND:
                continue

            # Input pins
            if pinn in outputs:
                self.PINS_DUT[pinn] = "o"
            else:
                self.PINS_DUT[pinn] = "i"

        self.PINS_DUT_IN = sum(
            [1 if x == "i" else 0 for x in self.PINS_DUT.values()])
        self.PINS_DUT_OUT = sum(
            [1 if x == "o" else 0 for x in self.PINS_DUT.values()])
        print("Calculated pins: %u input, %u output" %
              (self.PINS_DUT_IN, self.PINS_DUT_OUT))
        assert self.PINS_DUT_IN
        assert self.PINS_DUT_OUT

    def mk_pinmap(self):
        pinmap = {}
        inputs = 0
        outputs = 0
        for k, v in self.PINS_DUT.items():
            if v == "i":
                pinmap[k] = ("i", inputs)
                inputs += 1
            elif v == "o":
                pinmap[k] = ("o", outputs)
                outputs += 1
            else:
                assert 0
        return pinmap

    def pin_n2verilog(self, pin):
        """pin number to verilog name"""
        net, index = self.mk_pinmap()[pin]
        return "%s[%u]" % (net, index)

    def pin_n2vio(self, pin):
        """pin number to verilog io number"""
        return self.mk_pinmap()[pin]
