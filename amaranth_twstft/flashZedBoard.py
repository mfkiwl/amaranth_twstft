#!/usr/bin/env python3

from amaranth import *
from amaranth.build import *
from amaranth_boards.resources import *
from amaranth_twstft.Mixer import *

from amaranth_twstft.zedboard import *

import argparse

#default number of different taps to choose among when dynamically selecting the taps for the LFSR
nb_taps_auto = 32


class TWSTFT_top(Elaboratable):
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

    def __init__(self, bit_len, noise_len, reload=True, lock_pps_gen=True, taps = 0, seed = 0x1, freqout=2500000,
                 invert_first_code=False):
    
        self.pps_out = Signal()
        self.the_pps_we_love = Signal()
        self.dixmega = Signal()
        self.ref_clk = Signal()

        self._freqout = freqout
        self.mixer = Mixer(bit_len, noise_len, reload, lock_pps_gen, taps, seed, int(280e6), freqout,
                           invert_first_code)
        
    def elaborate(self,platform):
        m = Module()

        m.submodules.mixer = mixer = self.mixer

        m.domains.sync = ClockDomain()
        
        conna = ("pmoda",0)
        platform.add_resources([Resource('external_clk', 0,
                    Subsignal('A4_i', Pins('4',conn=conna, dir='i')),
                    Attrs(IOSTANDARD="LVCMOS33")
                )
            ])
        
        new_clk = platform.request('external_clk',0)
        
        platform_clk = new_clk.A4_i
        base_clk_freq    = 10000000
        mmcm_clk_out     = Signal()
        mmcm_locked      = Signal()
        mmcm_feedback    = Signal()
    
        clk_input_buf    = Signal()
        m.submodules += Instance("BUFG",
            i_I  = platform_clk,
            o_O  = clk_input_buf,
        )
        
        if base_clk_freq == 20000000:
            vco_mult = 42.0
            mmc_out_div = 3.0
        else:
            vco_mult = 63.0
            mmc_out_div = 2.25
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
        m.d.comb += ResetSignal("sync").eq(~mmcm_locked)
    
        clock_freq = 1e9/mmc_out_period
        print(f"clock freq {clock_freq} mmc out period {mmc_out_period}")
            
        #parametrizing the platforms outputs
        if (type(platform).__name__ == "ZedBoardPlatform"):
            connd = ("pmodd",0)
            connb = ("pmodb",0)
            connc = ("pmodc",0)
            
            platform.add_resources([
                Resource('pins', 0,
                    Subsignal('B1_o', Pins('1',  conn = connb, dir='o')),
                    Subsignal('B2_o', Pins('2',  conn = connb, dir='o')),
                    Subsignal('B3_o', Pins('3',  conn = connb, dir='o')),
                    Subsignal('B4_o', Pins('4',  conn = connb, dir='o')),
                    Subsignal('B5_o', Pins('7',  conn = connb, dir='o')),
                    Subsignal('B6_o', Pins('8',  conn = connb, dir='o')),
                    Subsignal('B7_o', Pins('9',  conn = connb, dir='o')),
                    Subsignal('B8_o', Pins('10', conn = connb, dir='o')),
                    
                    Subsignal('C1_i', Pins('1', conn = connc, dir='i')),
                    Subsignal('C2_i', Pins('2', conn = connc, dir='i')),
                    Subsignal('C4_i', Pins('4', conn = connc, dir='i')),
                    
                    Subsignal('D4_o', Pins('4', conn = connd, dir='o')),
                    Subsignal('D1_o', Pins('1', conn = connd, dir='o')),
                    Subsignal('D2_o', Pins('2', conn = connd, dir='o')), # invert_prn
                    Attrs(IOSTANDARD="LVCMOS33")
                )
            ])
        
        pins = platform.request('pins',0)
        
        #allowing to switch between BPSK and QPSK
        switch_mode = platform.request("switch", 0) #F22
        
        m.d.comb += [
            mixer.pps_in.eq(pins.C4_i),
            mixer.switch_mode.eq(switch_mode),
            mixer.global_enable.eq(pins.C1_i),
            mixer.output_carrier.eq(pins.C2_i),
        ]

        m.d.sync += pins.D4_o.eq(mixer.mod_out)

        if 1==1 : #debug ?
            m.d.sync+=[
                pins.B1_o.eq(mixer.the_pps_we_love),
                pins.B2_o.eq(mixer.dixmega),
                pins.B3_o.eq(mixer.pps_out),
                pins.B5_o.eq(mixer.output),
                pins.B6_o.eq(mixer.output2),
                pins.D2_o.eq(mixer.invert_prn_o),
                #pins.B4_o.eq(mixer.ref_clk),
                #pins.C1_o.eq(mmcm_locked),
            ]
        return m

#flasher le programme sur la carte SD manuellement :
#- brancher la carte microsd dans l'ordi avec l'adaptateur
#- flasher le programme en question
#- bash : 
#	bootgen -w -image toto.bif -arch zynq -process_bitstream bin
#	mount /mnt/removable
#	cp build/top.bit.bin / mnt/removable/system.bit.bin
#	umount /mnt/removable

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bitlen",       default=22,help="number of bits of the LFSR", type=int)
    parser.add_argument("--noiselen",     default=2.5e6,  help="length of the PRN sequence", type=float)
    parser.add_argument("--no-reload",    help="stop generation after noiselen bits", action="store_true")
    parser.add_argument("-s","--seed",    default=1, help="initial value of the LFSR (default 1)", type=int)
    parser.add_argument("-t","--taps",    help="taps positions for the LFSR (if not defined, allows to dynamically define taps (currently not supported so default taps will be the smallest msequence generator taps))", type=int)
    parser.add_argument("-m","--modfreq", default=int(2.5e6), help="frequency of the PSK modulation (Herz) (default :2.5e6)", type=int)
    parser.add_argument("--invert-first-code", help="invert (xor) the first code after PPS rise", action="store_true")
    parser.add_argument("-p","--print",   help="creates a binary file containing the PRN sequence that should be generated", action="store_true")
    parser.add_argument("-v","--verbose", help="prints all the parameters used for this instance of the program", action="store_true")
    parser.add_argument("--no-build",     help="sources generate only", action="store_true")
    parser.add_argument("--no-load",      help="don't load bitstream", action="store_true")
    parser.add_argument("--build-dir",    default="build", help="build directory")
    args = parser.parse_args()

    if args.taps :
        t = args.taps
    else:
        try:
            t = get_taps(args.bitlen)[0]
        except:
            taps_autofill(args.bitlen,32)
            t = get_taps(args.bitlen)[0]

    if args.print :
        write_prn_seq(args.bitlen, t, args.seed, seqlen=int(args.noiselen))

    invert_first_code = args.invert_first_code
    if invert_first_code and int(args.noiselen) >= int(args.modfreq):
        invert_first_code = False
        print(f"First code invertion disabled: noiselen ({args.noiselen}) >= modfreq ({args.modfreq})")

    if args.verbose:
        print("bit length of the LFSR : "+str(args.bitlen))
        print("number of bits generated per pps signal received : "+ str(args.noiselen))
        print("baseband signal frequency : "+str(args.modfreq))
        print("seed : "+str(args.seed))
        print("taps : "+ str(t))
        print("First code xoring: " + ("Enabled" if invert_first_code else "Disabled"))

    gateware = ZedBoardPlatform().build(
        TWSTFT_top(args.bitlen, int(args.noiselen), reload=not args.no_reload,
                   taps=t, seed=args.seed,
                   freqout=args.modfreq, invert_first_code=invert_first_code),
        do_program=not args.no_load, do_build=not args.no_build, build_dir=args.build_dir)
    # if no build nothing produces -> force
    if args.no_build:
        gateware.execute_local(args.build_dir, run_script=False)
