#!/usr/bin/python
from math import *
from scipy import signal 
import matplotlib.pyplot as plt
from scipy import arange
import numpy as np
import sys
from struct import *



def bits2bytes(bits):
  bytes =""
  by = 0
  c=0
  for b in bits:
    by =  (by << 1) | b
    c = c +1
    if(c & 7 == 0):
      bytes = bytes + chr(by)
      by=0
  return bytes

#fEU1	869.85	bw 300khz
#fEU2	868.40	bw 400khz
 
samp=2024000

#f =  open('test_sample3', 'r')
f =  open('zwave_100k.bin', 'r')

n=0

x=[]
y1=[]
y2=[]
sig=[]

while(True):
  n=n+1
  (re,im) = unpack("2B",f.read(2) )
  re = re - 127
  im = im - 127

  s = complex(re,im)
  sig.append( s )
  
  if(n>=500000):
    break;
  

#sp = np.fft.fft(y1)
#freq = np.fft.fftfreq(len(y1))*samp
#plt.plot(freq, sp.real,'g-', freq, sp.imag,'b-')
#plt.show()

sold=0

'''
Algorithm

The imput signal is on the form s(t) = a*exp(-i*w*t+p)
where a is the amplitude
w if the angular frequncy, (in reality w is a function of t but we will ignore that)
p if the phase difference

We wish to find w...

First we take the time derivative(s') of s
s' = -i(w+p)*a*exp(-i*w*t+p)

then we multiply s' by by conj(s) where conj is complex conjugation

s'*conj(s) = -i(w+p)*a*exp(-i*w*t+p)*a*exp(i*w*t + p)
           = -i(w+p)*a*a

finally we devide the result by the norm of s squared

s'*conj(s) / |s|^2 = -i(w+p)

Releated to the FSK demodulation, we know that w will fall out to two distinct values.
w1 and w2, and that w2-w1 = dw.

w will have the form w = wc +/- dw, where wc is the center frequnecy.

wc + p will show up as a DC component in the s'*conj(s) / |s|^2 function.
'''

#FSK decoder
n=0
s1=0
s2=0

for s in sig:

    p = np.abs(s) 
    if(p > 0 ):
      x.append(n)

      ds = (s-s2)/2 
      q = np.conj(s) * (ds / (p*p))
      y2.append( (q).imag )
      s1 = s
      s2 = s1
    n=n+1


Wn=120.0e3 / float(samp)
b,a =signal.butter(6, Wn, 'low')
y1 = signal.lfilter(b, a, y2)

Wn=12.0e3 / float(samp)
b,a =signal.butter(3, Wn, 'low')
lock_det = signal.lfilter(b, a, y2)

sig_detect = False
S_IDLE = 0
S_PREAMP = 1
S_DATA = 2
S_SOF = 3

n=0

pre_len=0 #Length of preamble bit
pre_cnt=0;

bit_len = 0
bit_cnt =0;

wc = 0 # center frequency
bits=[]
state = S_IDLE
dif=[]
last_logic=False
for s in y1:
  if(lock_det[n] > 0):    
    if(state == S_IDLE):
      state = S_PREAMP
      pre_cnt = 0
      pre_len = 0
    elif(state == S_PREAMP):
      wc = lock_det[n]
      logic = (s - wc) > 0
      pre_len = pre_len + 1
      if(logic ^ last_logic):
        pre_cnt = pre_cnt + 1
        #print pre_len
        #pre_len = 0
        if(pre_cnt==10): #skip the first 10
          pre_len =0;
        if(pre_cnt == 30):
          state = S_SOF
          bit_len = float(pre_len) / (pre_cnt-10)
          print bit_len
          bit_cnt = bit_len/2.0
      last_logic = logic
    elif(state == S_SOF):
      if(bit_cnt >= bit_len):
        #print logic
        bits.append( (s - wc) > 0 )
        bit_cnt= bit_cnt - bit_len 
      bit_cnt=bit_cnt +1.0

  else:
    if(state== S_SOF):
      print bits2bytes(bits).encode("hex")
      bits=[]

    #  break
    state = S_IDLE

  dif.append(s - wc)  
  n=n+1

#print len(dif)
plt.plot(x,y2)
plt.plot(x,y1)
plt.plot(x,dif)
plt.plot(x,lock_det)

plt.show()

sys.exit(0)

