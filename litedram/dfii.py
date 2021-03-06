# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *

from litedram.phy import dfi
from litex.soc.interconnect.csr import *

# PhaseInjector ------------------------------------------------------------------------------------

class PhaseInjector(Module, AutoCSR):
    def __init__(self, phase):
        self._command       = CSRStorage(6)  # cs, we, cas, ras, wren, rden
        self._command_issue = CSR()
        self._address       = CSRStorage(len(phase.address), reset_less=True)
        self._baddress      = CSRStorage(len(phase.bank),    reset_less=True)
        self._wrdata        = CSRStorage(len(phase.wrdata),  reset_less=True)
        self._rddata        = CSRStatus(len(phase.rddata))

        # # #

        self.comb += [
            If(self._command_issue.re,
                phase.cs_n.eq(Replicate(~self._command.storage[0], len(phase.cs_n))),
                phase.we_n.eq(~self._command.storage[1]),
                phase.cas_n.eq(~self._command.storage[2]),
                phase.ras_n.eq(~self._command.storage[3])
            ).Else(
                phase.cs_n.eq(Replicate(1, len(phase.cs_n))),
                phase.we_n.eq(1),
                phase.cas_n.eq(1),
                phase.ras_n.eq(1)
            ),
            phase.address.eq(self._address.storage),
            phase.bank.eq(self._baddress.storage),
            phase.wrdata_en.eq(self._command_issue.re & self._command.storage[4]),
            phase.rddata_en.eq(self._command_issue.re & self._command.storage[5]),
            phase.wrdata.eq(self._wrdata.storage),
            phase.wrdata_mask.eq(0)
        ]
        self.sync += If(phase.rddata_valid, self._rddata.status.eq(phase.rddata))

# DFIInjector --------------------------------------------------------------------------------------

class DFIInjector(Module, AutoCSR):
    def __init__(self, addressbits, bankbits, nranks, databits, nphases=1):
        inti        = dfi.Interface(addressbits, bankbits, nranks, databits, nphases)
        self.slave  = dfi.Interface(addressbits, bankbits, nranks, databits, nphases)
        self.master = dfi.Interface(addressbits, bankbits, nranks, databits, nphases)

        self._control = CSRStorage(4)  # sel, cke, odt, reset_n

        for n, phase in enumerate(inti.phases):
            setattr(self.submodules, "pi" + str(n), PhaseInjector(phase))

        # # #

        self.comb += If(self._control.storage[0],
                self.slave.connect(self.master)
            ).Else(
                inti.connect(self.master)
            )
        for i in range(nranks):
            self.comb += [phase.cke[i].eq(self._control.storage[1]) for phase in inti.phases]
            self.comb += [phase.odt[i].eq(self._control.storage[2]) for phase in inti.phases if hasattr(phase, "odt")]
        self.comb += [phase.reset_n.eq(self._control.storage[3]) for phase in inti.phases if hasattr(phase, "reset_n")]
