#!/usr/bin/env python3

from amaranth import *
from amaranth.build import *
from amaranth_boards.resources import *
from Synchronizer import *
from Prescaler import *



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

	def __init__(self, bit_len, noise_len, mode=1, taps = 0, seed = 0x1, freqout=2500000):
	
		self.carrier0 = Signal()
		self.carrier90 = Signal()
		self.modulatedI = Signal()
		self.modulatedQ = Signal()
		self._seed = seed
		self._noise_len = noise_len
		self._bit_len = bit_len
		self._mode = mode
		self._freqout = freqout
		
		if taps==0:
			self.dynamic_taps = True
			self.tsel = Signal(int(log(nb_taps_auto,2)))
		else:
			self.dynamic_taps = False
			self.taps = taps
		
	def elaborate(self,platform):
		m = Module()
		
		m.domains.sync = ClockDomain(reset_less=True)
		
		conna = ("pmoda",0)
		platform.add_resources([Resource('external_clk', 0,
					Subsignal('A4_i', Pins('4',conn=conna, dir='i')),
					Attrs(IOSTANDARD="LVCMOS33")
				)
			])
		
		new_clk = platform.request('external_clk',0)
		
		platform_clk = new_clk.A4_i
		base_clk_freq    = 20000000
		mmcm_clk_out     = Signal()
		mmcm_locked      = Signal()
		mmcm_feedback    = Signal()
	
		clk_input_buf    = Signal()
		m.submodules += Instance("BUFG",
			i_I  = platform_clk,
			o_O  = clk_input_buf,
		)
		
		vco_mult = 42.0
		mmc_out_div = 3.0
		mmc_out_period = 1e9 / (base_clk_freq * vco_mult / mmc_out_div)
				
		m.submodules.mmcm = Instance("MMCME2_BASE",
			p_BANDWIDTH          = "OPTIMIZED",
			p_CLKFBOUT_MULT_F    = vco_mult, 
			p_CLKFBOUT_PHASE     = 0.0,
			p_CLKIN1_PERIOD      = int(1e9 // base_clk_freq), # 20MHz
			
			
			p_CLKOUT0_DIVIDE_F   = mmc_out_div,
			p_CLKOUT0_DUTY_CYCLE = 0.5,
			p_CLKOUT0_PHASE      = 0.0,
			
	
			i_PWRDWN               = 0,
			i_RST                  = 0,
			i_CLKFBIN              = mmcm_feedback,
			o_CLKFBOUT             = mmcm_feedback,
			i_CLKIN1               = clk_input_buf,
			o_CLKOUT0              = mmcm_clk_out,
			o_LOCKED               = mmcm_locked,
		)
	
		m.submodules += Instance("BUFG",
			i_I  = mmcm_clk_out,
			o_O  = ClockSignal("sync"),
		)
	
		clock_freq = 1e9/mmc_out_period
		print(f"clock freq {clock_freq} mmc out period {mmc_out_period}")
			
		#parametrizing the platforms outputs
		if (type(platform).__name__ == "ZedBoardPlatform"):
			connd = ("pmodd",0)
			connb = ("pmodb",0)
			connc = ("pmodc",0)
			
			platform.add_resources([
				Resource('pins', 0,
					Subsignal('B1_o', Pins('1', conn = connb, dir='o')),
					Subsignal('B2_o', Pins('2', conn = connb, dir='o')),
					Subsignal('B3_o', Pins('3', conn = connb, dir='o')),
					Subsignal('B4_o', Pins('4', conn = connb, dir='o')),
					
					Subsignal('C1_o', Pins('1', conn = connc, dir='o')),
					Subsignal('C4_i', Pins('4', conn = connc, dir='i')),
					
					Subsignal('D4_o', Pins('4', conn = connd, dir='o')),
					Subsignal('D1_o', Pins('1', conn = connd, dir='o')),
					Attrs(IOSTANDARD="LVCMOS33")
				)
			])
		
		pins = platform.request('pins',0)
		
		#setting noise duration
		assert self._noise_len > 1
		
		#setting dynamic usage of taps
		if self.dynamic_taps :
			m.submodules.prn_gen = prn_gen = Synchronizer(clock_freq, 
															self._freqout,
															self._bit_len, 
															noise_len=self._noise_len, 
															seed = self._seed,
															mode = self._mode )
			m.d.comb += prn_gen.tsel.eq(self.tsel)
		else :
			m.submodules.prn_gen = prn_gen = Synchronizer(clock_freq, 
															self._freqout,
															self._bit_len, 
															noise_len=self._noise_len, 
															taps =self.taps, 
															seed = self._seed,
															mode = self._mode )
		
		
		carrier_selector = Signal()
		m.d.sync += carrier_selector.eq(~carrier_selector)
		
		with m.If(carrier_selector):
			m.d.sync += [
				self.carrier0.eq(~self.carrier0),
				self.modulatedI.eq(prn_gen.output ^ self.carrier0)
			]

			
		with m.Else():
			m.d.sync += [
				self.carrier90.eq(~self.carrier90),
				self.modulatedQ.eq(prn_gen.output2 ^ self.carrier90)
			]

		
		pps_1 = Signal()
		pps_2 = Signal()
		pps_old = Signal()
		rise_pps = Signal()
		m.d.sync += [
			pps_1.eq(pins.C4_i),
			pps_2.eq(pps_1),
			pps_old.eq(pps_2)
		]
		m.d.comb += rise_pps.eq((pps_2 ^ pps_old) & pps_2)
		m.d.comb += prn_gen.pps.eq(pins.C4_i)
		
			
		debug = Signal()
		with m.If(pps_1):
			m.d.sync+=debug.eq(~debug)
		
		m.d.comb += [
			pins.D1_o.eq(debug),
		]
		
				
		if self._mode == 2:
			m.d.sync += [
				#pins.D4_o.eq(Mux(prn_gen.output ^ prn_gen.output2, self.modulatedI,self.modulatedQ)),
				pins.D4_o.eq(self.modulatedI & self.modulatedQ),
				pins.B1_o.eq(prn_gen.output), #debug reasons
				pins.B2_o.eq(prn_gen.output2), #debug reasons
			]
		elif self._mode == 1 :
			m.d.sync += [
				pins.B1_o.eq(prn_gen.output), #debug reasons
				pins.D4_o.eq(self.modulatedI),
			]	
		return m

