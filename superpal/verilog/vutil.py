from collections import OrderedDict
import subprocess
import json
import re


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


"""
Parse view output generated from MAME's jedutil -view
"""


class ViewParser:
    def __init__(self, raw):
        # Output string from view file
        self.raw = raw
        # process as array of lines
        self.lines = None
        """
        Simple list of pin numbers
        """
        self.inputs = None
        """
        OrderedDict
        Given
        12 (Registered, Output feedback registered, Active low)
        Add
        self.outputs[12] = ["Registered", "Output feedback registered", "Active low"]

        13 (Combinatorial, Output feedback output, Active low)
        """
        self.outputs = None
        """
        List of nets
        OrderedDict()
        self[net] = (isinv, assign_type, terms)
        terms = ((net1, isinv), oper, (net2, isenv), oper, ...)


        Example:
        Given:
        /rf13 := /i4 & /i5 & i6 & i7 & /rf19 +
                 rf12 & /rf13 +
                 /rf12 & rf13
        rf13.oe = OE

        Gives:
        self.equataions['rf13'] = (True, ('rf', 13), ':=', [
                ('i4', True, ('i', 4)),
                '&',
                ('i5', True, ('i', 5)),
                '&',
                ('i6', False, ('i', 6)),
                ...])
        self.equataions['rf13.oe'] = (False, None, '=', [
                ('OE', False, None)])
        """
        self.equations = None

        self.reparse()

    def simplify_whitespace(self, viewtxt):
        """
        Make parsing simpler by reducing equations to one line
        """
        # not sure if this is actually needed
        viewtxt = viewtxt.replace("\r\n", "\n")
        viewtxt = viewtxt.replace("+\n", "+ ")
        # quick hack to remove duplicate spacing
        while True:
            start = viewtxt
            viewtxt = viewtxt.replace("\t", " ")
            viewtxt = viewtxt.replace("  ", " ")
            if start == viewtxt:
                break
        return viewtxt

    def pop_line(self):
        ret = self.lines[0]
        del self.lines[0]
        return ret.strip()

    def wait_line(self, s):
        while s not in self.pop_line():
            pass

    def parse_term_net(self, x):
        """
        Ex: "i7"
        Return: 
    
        Ex: "/rf19"
        Return:
        """
        assert " " not in x
        inverted = False
        if x[0] == '/':
            inverted = True
            x = x[1:]
        net = x
        m = re.match("([iorf]+)([0-9]+)", x)
        assert m, ("Expected net", x)
        bus = m.group(1)
        assert bus in ("i", "o", "rf"), x
        pinn = int(m.group(2))
        return (net, inverted, bus, pinn)

    def parse_inputs(self):
        self.wait_line("Inputs:")
        assert self.pop_line() == ""
        # 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17, 18, 19
        self.inputs = [int(x) for x in self.pop_line().split(",")]

    def parse_outputs(self):
        self.wait_line("Outputs:")
        assert self.pop_line() == ""
        self.outputs = OrderedDict()
        while True:
            l = self.pop_line()
            if l == "":
                break
            """
            OrderedDict
            Given
            12 (Registered, Output feedback registered, Active low)
            Add
            self.outputs[12] = ["Registered", "Output feedback registered", "Active low"]
            """
            m = re.match("([0-9]+) [(](.*), (.*), (.*)[)]", l)
            assert m
            pinn = int(m.group(1))
            self.outputs[pinn] = (m.group(2), m.group(3), m.group(4))

    def parse_equations(self):
        self.wait_line("Equations:")
        self.equations = OrderedDict()

        # gen_io_pindirs(lines)
        print('looping for logic defs')
        # propagate potential loops to new definitions on metadata['looped']

        while self.lines:
            l = self.pop_line()
            if not l:
                continue

            # fixme: hack skip oe for now since I don't care about them
            if ".oe = " in l:
                continue

            m = re.match("(.*) ([\:=]+) (.*)", l)
            assert m, l
            lhs = m.group(1)
            oper = m.group(2)
            rhs = m.group(3)

            lhs_net, lhs_isinv, lhs_bus, lhs_pinn = self.parse_term_net(lhs)
            terms = []
            for termi, term in enumerate(rhs.split(" ")):
                if termi % 2 == 0:
                    rhs_net, rhs_isinv, rhs_bus, rhs_pinn = self.parse_term_net(
                        term)
                    terms.append((rhs_net, rhs_isinv, (rhs_bus, rhs_pinn)))
                else:
                    assert term in "&+"
                    terms.append(term)

            self.equations[lhs_net] = (lhs_isinv, (lhs_bus, lhs_pinn), oper,
                                       terms)

    def reparse(self):
        self.lines = self.simplify_whitespace(self.raw).split("\n")
        self.parse_inputs()
        self.parse_outputs()
        self.parse_equations()

    def save_parsed(self, fn):
        j = {
            "inputs": self.inputs,
            "outputs": self.outputs,
            "equations": self.equations,
        }

        open(fn, "w").write(
            json.dumps(j, sort_keys=True, indent=4, separators=(',', ': ')))


class PAL:
    def __init__(self):
        # TODO: convert to pin map per device type
        self.PIN_GND = 10
        self.PIN_VCC = 20
        self.PINS_DUT = None
        self.metadata = None
        self.view = None
        self.verilog_pinmap = None

    def part(self):
        """Return part such as PAL16L8"""
        assert 0, "Must be implemented"

    def verilog_write(self, fn_out):
        assert 0, "Must be implemented"

    def i_to_binstr(self, x):
        return pad_(format(x, '0%ub' % self.get_npins_in()))

    def o_to_binstr(self, x):
        return pad_(format(x, '0%ub' % self.get_npins_out()))

    def is_io_pinn(self, pinn):
        return pinn not in (self.PIN_GND, self.PIN_VCC)

    def gen_io_pindirs(self):
        """
        Create a high level mapping of pin number to whether input or output
        """

        self.PINS_DUT = OrderedDict([])

        # Now order pins
        for pinn in range(1, 21):
            if not self.is_io_pinn(pinn):
                continue

            # Don't worry about latches, FFs, internal feedback, etc
            # View includes outputs in inputs since they can loop back
            # However outputs seem to be reliable
            if pinn in self.view.outputs:
                self.PINS_DUT[pinn] = "o"
            else:
                self.PINS_DUT[pinn] = "i"

        print("Calculated pins: %u input, %u output" %
              (self.get_npins_in(), self.get_npins_out()))
        assert self.get_npins_in()
        assert self.get_npins_out()

    def get_npins_in(self):
        # Formerly PINS_DUT_IN
        return sum([1 if x == "i" else 0 for x in self.PINS_DUT.values()])

    def get_npins_out(self):
        # Formerly PINS_DUT_OUT
        return sum([1 if x == "o" else 0 for x in self.PINS_DUT.values()])

    def mk_verilog_pinmap(self):
        """
        ret[pin_number] = (bus_name, index)
        """

        self.verilog_pinmap = {}
        inputs = 0
        outputs = 0
        for k, v in self.PINS_DUT.items():
            if v == "i":
                self.verilog_pinmap[k] = ("i", inputs)
                inputs += 1
            elif v == "o":
                self.verilog_pinmap[k] = ("o", outputs)
                outputs += 1
            else:
                assert 0

    def pin_n2verilog(self, pin):
        """pin number to verilog name"""
        assert 1 <= pin <= 20
        net, index = self.verilog_pinmap[pin]
        return "%s[%u]" % (net, index)

    def pin_n2vio(self, pin):
        """pin number to verilog io number"""
        assert 1 <= pin <= 20
        return self.verilog_pinmap[pin]

    def view_to_verilog_terms(self):
        # output net name to equation
        terms = {}
        for (_lhs_net, equation) in self.view.equations.items():
            _lhs_isinv, (_lhs_bus, lhs_pinn), _oper, rhs_terms = equation
            vterms = []
            for termi, term in enumerate(rhs_terms):
                # Term
                if termi % 2 == 0:
                    _rhs_net, rhs_isinv, (_rhs_bus, rhs_pinn) = term
                    inverted = "~" if rhs_isinv else ""
                    vterms.append(inverted + self.pin_n2verilog(rhs_pinn))
                # Operator
                else:
                    operator = term.replace("/", "~").replace("+", "|")
                    vterms.append(operator)

            vnet_out = self.pin_n2verilog(lhs_pinn)
            terms[vnet_out] = '~(%s)' % (' '.join(vterms), )
        return terms

    def jed_to_verilog(self,
                       jed_fn_in,
                       v_fn_out,
                       view_fn=None,
                       view_j_fn=None,
                       metadata_fn=None):
        print("Converting to view (%s)" % (self.part(), ))
        raw = subprocess.check_output("jedutil -view %s %s" %
                                      (jed_fn_in, self.part()),
                                      shell=True,
                                      encoding="ascii")
        if view_fn:
            open(view_fn, "w").write(raw)
        self.view = ViewParser(raw)
        # Debug dump to view AST
        if view_j_fn:
            self.view.save_parsed(view_j_fn)

        self.gen_io_pindirs()
        self.mk_verilog_pinmap()

        self.create_sim_mask()
        # Convert view AST to verilog AST
        terms = self.view_to_verilog_terms()
        self.verilog_write(terms, v_fn_out)

        # This is required across program runs in some situations
        self.metadata = {
            'looped': self.looped,
            "pins_dut": self.PINS_DUT,
            "npins_dut_in": self.get_npins_in(),
            "npins_dut_out": self.get_npins_out(),
        }
        if metadata_fn:
            open(metadata_fn, "w").write(
                json.dumps(self.metadata,
                           sort_keys=True,
                           indent=4,
                           separators=(',', ': ')))
