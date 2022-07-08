#!/usr/bin/env python3

import os
import subprocess
from os.path import exists
from amaranth.build import *
from amaranth.vendor.xilinx import *
from amaranth_boards.resources import *
import argparse

__all__ = ["ZedBoardPlatform"]

class ZedBoardPlatform(XilinxPlatform):
    device = "xc7z020"
    package = "clg484"
    speed = "1"
    default_clk = "clk100"
    resources = [
        Resource("clk100", 0, Pins("Y9", dir="i"),
                 Clock(100e6), Attrs(IOSTANDARD="LVCMOS33")),

        Resource("userclk", 0, Pins("AA9", dir="i"), # pmoda.4
                 Clock(20e6), Attrs(IOSTANDARD="LVCMOS33")),

        *SwitchResources(
            pins="F22 G22 H22 F21 H19 H18 H17 M15",
            attrs=Attrs(IOSTANDARD="LVCMOS18")),

        *ButtonResources(
            pins="P16 R16 N15 R18 T18",
            attrs=Attrs(IOSTANDARD="LVCMOS18")),

        *LEDResources(
            pins="T22 T21 U22 U21 V22 W22 U19 U14",
            attrs=Attrs(IOSTANDARD="LVCMOS33")),
    ]
    connectors = [
        Connector("pmoda", 0, "Y11 AA11 Y10 AA9 - - AB11 AB10 AB9 AA8 - -"),
        Connector("pmodb", 0, "W12 W11  V10 W8  - - V12  W10  V9  V8  - -"),
        Connector("pmodc", 0, "AB7 AB6  Y4  AA4 - - R6   T6   T4  U4  - -"),
        Connector("pmodd", 0, "V7  W7   V5  V4  - - W6   W5   U6  U5  - -"),
    ]

    def toolchain_program(self, products, name, **kwargs):
        tool = os.environ.get("OPENFPGALOADER", "openFPGALoader")
        with products.extract("{}.bit".format(name)) as bitstream_filename:
            print(bitstream_filename)
            print(os.getcwd())
            print(name)
            subprocess.check_call([tool, "-b", "zedboard", '--freq', '30e6', '-m', bitstream_filename])
            if exists(bitstream_filename + ".bin"): 
            	os.remove(bitstream_filename + ".bin")
            with open(name+".bif", "w") as fd:
                fd.write("all:\n")
                fd.write("{\n")
                fd.write(f"\t{bitstream_filename}\n")
                fd.write("}\n")
            subprocess.check_call(["bootgen", "-w", "-image", name + ".bif", "-arch", "zynq", "-process_bitstream", "bin"])
            os.remove(name+".bif")
    

#flasher le programme sur la carte SD manuellement :
#- brancher la carte microsd dans l'ordi avec l'adaptateur
#- flasher le programme en question
#- bash : 
#	bootgen -w -image toto.bif -arch zynq -process_bitstream bin
#	mount /mnt/removable
#	cp build/top.bit.bin / mnt/removable/system.bit.bin
#	umount /mnt/removable

if __name__ == "__main__":
    from Mixer import *
    from prn import *
    parser = argparse.ArgumentParser()
    parser.add_argument("bitlen", help="number of bits of the LFSR", type=int)
    parser.add_argument("noiselen", help="length of the PRN sequence", type=int)
    parser.add_argument("-s","--seed", help="initial value of the LFSR (default : 1)",default=1, type=int)
    parser.add_argument("-t","--taps", help="taps positions for the LFSR (if not defined, allows to dynamically define taps (currently not supported so the program will ask you which taps to use))", type=int)
    parser.add_argument("-m","--modfreq", help="frequency of the PSK modulation (Herz) (default :2.5e6)", default=2500000,type=int)
    parser.add_argument("-p","--print", help="creates a binary file containing the PRN sequence that should be generated", action="store_true")
    parser.add_argument("-v","--verbose", help="prints all the parameters used for this instance of the program", action="store_true")
    args = parser.parse_args()
    s = args.seed
    f = args.modfreq
    if args.taps :
        t = args.taps
    else:
        taps_autofill(args.bitlen,32)
        taps_list = get_taps(args.bitlen)
        choice = input(f"Choose your taps among \n{taps_list} : ")
        while(not(int(choice) in taps_list)):
            print(f"\n{choice} is not a correct value for a {args.bitlen}-bits PRN")
            choice = input(f"Choose your taps among \n{taps_list} : ")
        t = int(choice)
        print()
    if args.print :
        write_prn_seq(args.bitlen, t, s, seqlen = args.noiselen)
        exit()
    if args.verbose:
        print("bit length of the LFSR : "+str(args.bitlen))
        print("number of bits generated per pps signal received : "+ str(args.noiselen))
        print("baseband signal frequency : "+str(f))
        print("seed : "+str(s))
        print("taps : "+ str(t))

    ZedBoardPlatform().build(
                            Mixer(
                                args.bitlen,
                                args.noiselen, 
                                taps = t, 
                                seed = s, 
                                freqout=f
                            ), do_program=True)
