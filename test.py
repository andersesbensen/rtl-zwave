#!/usr/bin/python
from math import *
from scipy import signal 
import matplotlib.pyplot as plt
from scipy import arange
import numpy as np
import sys
from struct import *
from scipy.signal import firwin


def zwave_print(frame):
    if(len(frame) < 7):
        print "Short: " + frame.encode("hex")
    else:
        l = ord(frame[7])
        print "Frame: " + frame[0:l].encode("hex"),
        print "  trailer " + frame[l+1:].encode("hex"),
#        print " CRC", hex(CrcSum16(frame[0:l-2]))        
        print
    
def bits2bytes(bits):
    r = ""
    by = 0
    c = 0
    for b in bits:
        by = (by << 1) | b
        c = c + 1
        if(c & 7 == 0):
            r = r + chr(by)
            by = 0
    return r
  

# Several flavors of bandpass FIR filters.

def bandpass_firwin(ntaps, lowcut, highcut, fs, window='hamming'):
    nyq = 0.5 * fs
    taps = firwin(ntaps, [lowcut, highcut], nyq=nyq, pass_zero=False,
                  window=window, scale=False)
    return taps  

# fEU1	869.85	bw 300khz
# fEU2	868.40	bw 400khz
 
samp = 2024000

# f =  open('test_sample3', 'r')
f = open('zwave_100k.bin', 'r')

n = 0

x = []
y1 = []
y2 = []
sig = []

while(True):
    n = n + 1
    (re, im) = unpack("2B", f.read(2))
    re = re - 127
    im = im - 127
    
    s = complex(re, im)
    sig.append(s)
  
    if(n >= 500000):
        break;
  

# sp = np.fft.fft(sig)
# freq = np.fft.fftfreq(len(sig)) * samp
# plt.plot(freq, sp.real, 'g-', freq, sp.imag, 'b-')
# plt.show()

sold = 0



taps = bandpass_firwin(128, 400e3 - 150e3, 400e3 + 150e3, samp)
'''
Algorithm

The imput signal is on the form s(t) = a*exp(-i*w*t+p)
where a is the amplitude
w if the angular frequncy, (in reality w is a function of t but we will ignore that)
p if the phase difference

We wish to find w...

First we take the time derivative(s') of s
s' = -i(w)*a*exp(-i*w*t+p)

then we multiply s' by by conj(s) where conj is complex conjugation

s'*conj(s) = -i(w)*a*exp(-i*w*t+p)*a*exp(i*w*t + p)
           = -i(w)*a*a

finally we devide the result by the norm of s squared

s'*conj(s) / |s|^2 = -i(w+p)

Releated to the FSK demodulation, we know that w will fall out to two distinct values.
w1 and w2, and that w2-w1 = dw.

w will have the form w = wc +/- dw, where wc is the center frequnecy.

wc + p will show up as a DC component in the s'*conj(s) / |s|^2 function.
'''

# FSK decoder
n = 0
s1 = 0
s2 = 0

for s in sig:
    p = np.abs(s) 
    if(p > 0):
        x.append(n)        
        ds = (s - s2) / 2 
        q = (np.conj(s1) * ds) / (p * p)
        y2.append(-q.imag)
        s2 = s1
        s1 = s
        
    n = n + 1


Wn = 120.0e3 / float(samp)
b, a = signal.butter(6, Wn, 'low')
y1 = signal.lfilter(b, a, y2)

Wn = 12.0e3 / float(samp)
b, a = signal.butter(3, Wn, 'low')
print b
print a
lock_det = signal.lfilter(b, a, y2)

S_IDLE = 0
S_PREAMP = 1
S_BITLOCK = 3

B_PREAMP = 1
B_SOF0 = 2
B_SOF1 = 3
B_DATA = 4

n = 0

pre_len = 0  # Length of preamble bit
pre_cnt = 0;

bit_len = 0
bit_cnt = 0.0;

wc = 0  # center frequency
bits = []
state = S_IDLE
dif = []
last_logic = False
lead_in = 10

for s in y1:
    logic = (s - wc) > 0
    if(lock_det[n] < 0):    #DO this does not hold...
        if(state == S_IDLE):
            state = S_PREAMP
            pre_cnt = 0
            pre_len = 0
        elif(state == S_PREAMP):
            wc = lock_det[n]            
            pre_len = pre_len + 1
            if(logic ^ last_logic): #edge trigger (rising and falling)
                pre_cnt = pre_cnt + 1
            
            if(pre_cnt == lead_in):  # skip the first lead_in
                pre_len = 0;
            elif(pre_cnt > 30):
                state = S_BITLOCK
                state_b = B_PREAMP
                
                bit_len = float(pre_len) / (pre_cnt - lead_in)
                #print bit_len
                bit_cnt = bit_len / 2.0
                last_bit = not logic
        elif(state == S_BITLOCK):
            if(logic ^ last_logic):
                bit_cnt = bit_len / 2.0 #Re-sync on edges
            else:
                bit_cnt = bit_cnt + 1.0    

            if(bit_cnt >= bit_len): # new bit
                if(state_b == B_PREAMP):
                    if( logic and last_bit):
                        state_b = B_SOF1
                        b_cnt = 1 #This was the first SOF bit
                elif(state_b == B_SOF0):
                    if( not logic ):
                        b_cnt = b_cnt +1
                        if(b_cnt == 4):
                            b_cnt = 0
                            state_b = B_DATA
                    else:
                        print "SOF 0 error",b_cnt
                        state = S_IDLE
                elif(state_b == B_SOF1):
                    if( logic ):
                        b_cnt = b_cnt +1
                        if(b_cnt == 4):
                            b_cnt = 0
                            state_b = B_SOF0
                    else:
                        print "SOF 1 error"
                        state = S_IDLE
                elif(state_b == B_DATA):
                    # print logic
                    bits.append(logic)
                
                last_bit = logic
                bit_cnt = bit_cnt - bit_len
    else: # No LOCK
        if(state == S_BITLOCK):
            frame = bits2bytes(bits)
            zwave_print(frame)
            bits = []
    
        #  break
        state = S_IDLE

    last_logic = logic    
    dif.append(s - wc)  
    n = n + 1

# print len(dif)
plt.plot(x, y2)
plt.plot(x, y1)
plt.plot(x, dif)
plt.plot(x, lock_det)

plt.show()

sys.exit(0)

