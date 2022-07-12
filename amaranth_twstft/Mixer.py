#!/usr/bin/env python3

from amaranth import *
from amaranth.build import *
from amaranth_boards.resources import *
from amaranth_twstft.Synchronizer import *
from amaranth_twstft.Prescaler import *



#default number of different taps to choose among when dynamically selecting the taps for the LFSR
nb_taps_auto = 32


class Mixer(Elaboratable):
    """
    A module that generates 70MHz BPSK signal modulated by a n-bits 1PPS-synchronized Pseudo-Random Noise sequence.
    ZedBoard compatible.
    
    Parameters
    ----------
    bit_len : positive integer
        number of bits of the LFSR
    
    noise_len : positive integer
        number of bits that should be generated by the Pseudo-Random Noise Generator befor any reset
        
    taps : non negative integer 
        taps that should be used for the LFSR (set to 0 by default, 0 means the taps are chosen dynamically)
    
    seed : positive integer
        initial state of the LFSR (1 by default)
    
    Attributes
    ----------
    carrier : Signal()
        The signal to be modulated by the PRN
    
    mudulated : Signal()
        the output signal of the module
        the value of the carrier signal modulated by our PRN
    
    _seed : positive integer
        the initial state of the LFSR
        (1 by default)
    
    _noise_len : integer
        the number of PRN bits to generate before the end of 
        the next automatic reset of the LFSR state 
    
    _bit_len : positive integer
        number of bits of the LFSR
    
    """

    def __init__(self, bit_len, noise_len, taps = 0, seed = 0x1, freqin = 280e6, freqout=2500000):
    
        self.carrier0 = Signal()
        self.carrier90 = Signal()
        self.modulatedI = Signal()
        self.modulatedQ = Signal()
        self.mod_out    = Signal()
        self.pps_in     = Signal()
        
        # debug
        self.pps_out         = Signal()
        self.the_pps_we_love = Signal()
        self.dixmega         = Signal()
        self.ref_clk         = Signal()

        # ctrl
        self.global_enable = Signal()
        self.switch_mode   = Signal()

        self._seed = seed
        self._noise_len = noise_len
        self._bit_len = bit_len
        self._freqout = freqout
        self.clock_freq = freqin
        
        if taps==0:
            self.dynamic_taps = True
            self.tsel = Signal(int(log(nb_taps_auto,2)))
        else:
            self.dynamic_taps = False
            self.taps = taps
        
    def elaborate(self,platform):
        m = Module()
        
        #setting noise duration
        assert self._noise_len > 1
        
        #setting dynamic usage of taps
        if self.dynamic_taps :
            m.submodules.prn_gen = prn_gen = Synchronizer(self.clock_freq, 
                                                            self._freqout,
                                                            self._bit_len, 
                                                            noise_len=self._noise_len, 
                                                            seed = self._seed)
            m.d.comb += prn_gen.tsel.eq(self.tsel)
        else :
            m.submodules.prn_gen = prn_gen = Synchronizer(self.clock_freq, 
                                                            self._freqout,
                                                            self._bit_len, 
                                                            noise_len=self._noise_len, 
                                                            taps =self.taps, 
                                                            seed = self._seed)
                
                
        carrier_selector = Signal()
        m.d.sync += carrier_selector.eq(~carrier_selector) #alternating the carrier to modulate
        
        with m.If(carrier_selector):
            m.d.sync += [
                self.carrier0.eq(~self.carrier0),
                self.modulatedI.eq(prn_gen.output ^ self.carrier0) #alternating the carrier to modulate
            ]

            
        with m.Else():
            m.d.sync += [
                self.carrier90.eq(~self.carrier90),
                self.modulatedQ.eq(prn_gen.output2 ^ self.carrier90) #alternating the carrier to modulate
            ]

        m.d.comb += [
            prn_gen.pps.eq(self.pps_in),
        ]
        
        with m.If(self.global_enable):# put to 1 if you want to start generating on the pps rising edge
            #Defining if we are using BPSK (1) or QPSK (2)
            with m.If(self.switch_mode):
                m.d.comb+= prn_gen.mode.eq(1)
                m.d.sync += [
#                    pins.D4_o.eq(Mux(prn_gen.output ^ prn_gen.output2, self.modulatedI,self.modulatedQ)),
                    self.mod_out.eq(self.modulatedI & self.modulatedQ),
#                    pins.B1_o.eq(prn_gen.output), #debug reasons
#                    pins.B2_o.eq(prn_gen.output2), #debug reasons
                ]
            with m.Else():
                m.d.comb+= prn_gen.mode.eq(0)
                m.d.sync += [
#                    pins.B1_o.eq(prn_gen.output), #debug reasons
                    self.mod_out.eq(self.modulatedI),
                ]
        if 1==1 : #debug ?
        
            m.submodules.vingtmega = presc20MHz = Prescaler(self.clock_freq,20000000)
            m.submodules.highstate200ns = hs200ns = GlobalCounter(56000000)
            the_pps_we_love = Signal()
            dixmega = Signal()
            
            m.d.comb += [
                presc20MHz.enable.eq(1),
                hs200ns.tick.eq(1),
                the_pps_we_love.eq(hs200ns.output),
            ]
            with m.If(presc20MHz.output):
                m.d.sync += dixmega.eq(~dixmega)
            
            m.d.sync+=[
                hs200ns.reset.eq(prn_gen.rise_pps),
                self.the_pps_we_love.eq(the_pps_we_love),
                self.dixmega.eq(dixmega),
                self.pps_out.eq(self.pps_in),
                #pins.B4_o.eq(new_clk.A4_i),
                #pins.C1_o.eq(mmcm_locked),
            ]
        return m

