from math import ceil
from amaranth import *
from amaranth.sim import *

class Prescaler(Elaboratable):
    """A prescaler implementation to demultiply the clock signal
    Parameters
    ----------
    freqin : int or float
        the frequency we intend to  use in our FPGA

    freqout :non zero int or float
        the frequency of the output signal rising edge
    Attributes
    ----------
    output : Signal()
    _ticks_per_period : int
        number of clock ticks between each output rising edge
    _cnt : Signal(32)
        number of ticks waited since the last output rising edge
    enable : Signal()
        input signal that should be set to 0 if we want to force the prescaler
        to wait in its initial state, to one if we want to read its output
    """

    def __init__(self,freqin,freqout):
        self._ticks_per_period = ceil(freqin/freqout)
        print(f"freqin {freqin} | freqout {freqout} | ticks per period {self._ticks_per_period}")
        self._cnt = Signal(range(0, self._ticks_per_period), reset=0,name="presc_counter")
        self.output = Signal(1, reset=0,name="presc_output")
        self.enable = Signal(1,name="presc_enable")

    def elaborate(self, platform):
        m = Module()
        #m.d.comb += self.output.eq(0)

        cnt_next = Signal(range(self._ticks_per_period), reset_less=True)
        m.d.comb += cnt_next.eq(self._cnt + 1)

        reset = cnt_next == self._ticks_per_period-1

        m.d.sync += self.output.eq(Mux(reset, 1, 0))

        m.d.sync += self._cnt.eq(cnt_next)
        with m.If((self._cnt == (self._ticks_per_period-1)) | ~self.enable):
            m.d.sync += self._cnt.eq(self._cnt.reset)
            #m.d.comb += self.output.eq(1)

        #with m.If(!self.enable):
        #    m.d.sync += self._cnt.eq(self._cnt.reset)
        """
        with m.If(self.enable):
            with m.If(self._cnt == (self._ticks_per_period-1)):
                m.d.sync += self._cnt.eq(self._cnt.reset)
                m.d.comb += self.output.eq(1)
            with m.Else():
                m.d.sync += self._cnt.eq(self._cnt +1)
        with m.Else():
            m.d.sync += self._cnt.eq(0)
        """
        return m


if __name__ == "__main__":
    freqin = 10e6
    dut = Prescaler(freqin,1e6)
    sim = Simulator(dut)

    def proc():
        yield dut.enable.eq(1)
        #test for the normal use of the prescaler
        for i in range(204):
            yield Tick()

        #test for the stop of the output signal with ~enable
        yield dut.enable.eq(0)
        for i in range(100):
            yield Tick()

        #test for the return of the normal use of the prescaler
        yield dut.enable.eq(1)
        for i in range(200):
            yield Tick()

    sim.add_clock(1/freqin)
    sim.add_sync_process(proc)
    with sim.write_vcd("test.vcd"):
        sim.run()
