# Copyright 2021 Eric Schlaepfer
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

# bits in the jedec file:
# 0 means unblown, low resistance link
# 1 means blown, high resistance link

# product term is true when all inputs to it are high
# therefore, if both the normal and complement version of a signal
# are present in a product term, the output is always low.

# therefore a product term of all 0s means the output is always low.
# but a product term of all 1s means the output is always true.


def main():
    import argparse

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('jed_in')
    args = parser.parse_args()

    f = open(args.jed_in, 'r')
    data = f.readlines()
    f.close()

    # crappy jedec parser
    allbits = []
    for l in data:
        l = l.strip()
        if l[0] == 'L':
            _addr = int(l[1:6])
            bits = l[7:-1]
            allbits.append(bits)
    allbits = ''.join(allbits)

    # TODO: move these into a config/net name file
    inputnames = [
        'CYC0', 'CYC1', 'CYC2', 'CYC3', 'INT_S0#', 'INT_S1#', 'INT_S2#',
        'HIGH_BYTE'
    ]

    #outputnames = []
    #for i in range(8):
    #    outputnames.append('O%d' % (i+1))

    # TODO: move these into a config/net name file
    outputnames = ['O1', 'O2', 'UNK5', 'O4', 'U58_LE', 'UNK2', 'UNK3', 'O8']

    # generate the english names for each input to the matrix
    termnames = []
    for i in range(8):
        #termnames.append('I%d' % (i+2))
        #termnames.append('!I%d' % (i+2))
        termnames.append('%s' % (inputnames[i]))
        termnames.append('!%s' % (inputnames[i]))
        #termnames.append('O%d' % (i+1))
        #termnames.append('!O%d' % (i+1))
        termnames.append('%s' % (outputnames[i]))
        termnames.append('!%s' % (outputnames[i]))

    # TODO: fix magic numbers
    # each output has 8 sum terms. (for the R. the L has an OE and 7 terms)
    for outp in range(8):
        list_sums = []
        terms = allbits[(256 * outp):(256 * (outp + 1))]
        for st in range(8):
            list_prods = []
            proterm = terms[(32 * st):(32 * (st + 1))]
            # process product term
            # if it is 1111..., then it is fixed at a logic high
            # this means the corresponding output is always high.
            if not ('0' in proterm):
                list_prods = [1]
                list_sums.append('1')
            # if it is 0000...., then it is fixed at a logic low
            # this means we get to skip this sum term
            elif not ('1' in proterm):
                pass
            else:
                for pt in range(32):
                    if proterm[pt] == '0':
                        list_prods.append(termnames[pt])
                list_sums.append('(' + ' & '.join(list_prods) + ')')
        #print(list_sums)
        print(outputnames[outp] + ' = ' + ' | '.join(list_sums))
        print('\n')
