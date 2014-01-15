#!/usr/bin/python
from math import *
from scipy import signal 
import matplotlib.pyplot as plt
from scipy import arange
import numpy as np
import sys
from struct import *
#fEU1	869.85	bw 300khz
#fEU2	868.40	bw 400khz
 
samp=2024000

base_freq =868.3e6
center=62e3


#sep = 58e3
sep = 40e3
#f1 = 
#f2 = 


hi_speed=False
f1 =46e3  if(hi_speed) else center-sep/2.0
f2 = 50e3 if(hi_speed) else center+sep/2.0
print "f1,f2",f1,f2

f1 = 154e3
f2 = 194e3
T1 = (samp/f1)
T2 = (samp/f2)


print "T1,T2",T1,T2

T1n=int(T1+0.5)
T2n=int(T2+0.5)

print "T1,T2",T1,T2,T1n,T2n

#f =  open('test_sample3', 'r')
f =  open('zwave_100k.bin', 'r')

n=0

x=[]
y1=[]
y2=[]
sig=[]


w1 = 2*pi / T1
w2 = 2*pi / T2

#dt
base_freq=62e3
w = 2*pi*base_freq/samp

sold = 0

ws = (pi/2)*sep/samp


while(True):
  n=n+1
  (re,im) = unpack("2B",f.read(2) )
  re = re - 127
  im = im - 127
  #Down convert base_band
  
  #s = complex(re,im)* np.exp(-1j * w*n)
  s = complex(re,im)
  sig.append( s )
  #y1.append(s * sig[-int(ws)])
  y1.append(s)
  
  if(n>=500000):
    break;
  

#sp = np.fft.fft(y1)
#freq = np.fft.fftfreq(len(y1))*samp
#plt.plot(freq, sp.real,'g-', freq, sp.imag,'b-')
#plt.show()

sold=0

'''
Algorithm

The imput signal is on the form s(t) = a*exp(-i*(w + p)*t)
where a is the amplitude
w if the angular frequncy, (in reality w is a function of t but we will ignore that)
p if the phase difference

We wish to find w...

First we take the time derivative(s') of s
s' = -i(w+p)*a*exp(-i*(w + p)*t)

then we multiply s' by by conj(s) where conj is complex conjugation

s'*conj(s) = -i(w+p)*a*exp(-i*(w + p)*t)*a*exp(i*(w + p)*t)
           = -i(w+p)*a*a

finally we devide the result by the norm of s squared

s'*conj(s) / |s|^2 = -i(w+p)

Releated to the FSK demodulation, we know that w will fall out to two distinct values.
w1 and w2, and that w2-w1 = dw.

w will have the form w = wc +/- dw, where wc is the center frequnecy.

wc + p will show up as a DC component in the s'*conj(s) / |s|^2 function.
'''



n=0
qold = 0
y1d = np.gradient(np.array(sig),1)
for s in y1:
    #print np.abs(s)    
    p = np.abs(s) 
    if(p > 60 ):
      x.append(n)
      q = np.conj(s) * y1d[n] / (p*p)
      y2.append( (q).imag )
      qold = q
    n=n+1

#TODO detect the DC component of the preamble
dc=8700

Wn=120.0e3 / float(samp)
b,a =signal.butter(6, Wn, 'low')
y1 = signal.lfilter(b, a, y2)
    

plt.plot(sig)
plt.plot(x,y2)
plt.plot(x,y1)
plt.show()

sys.exit(0)


while(True):
  (re,im) = unpack("2B",f.read(2) )

  n=n+1
  s = re-127
  sig.append(s)

  #if(abs(s) > 50):
  if(True):    
    if(n > T1n and n > T2n):
	#y1.append(s*sin(2*pi/T1 * n))
	#y2.append(s*sin(2*pi/T2 * n))

    	x.append(n)
        
    	N=2
    	ss=s
        for i in range(1,N):
          ss=ss + (sig[n-int(i*T1+0.5)-1])
	y1.append(ss*ss / ((N+1)*(N+1)) )

    	ss=s
        for i in range(1,N):
          ss=ss + (sig[n-int(i*T2+0.5)-1] )
	y2.append(ss*ss / ((N+1)*(N+1)) )

    	
  if(n>=1000000):
    break;


plt.plot(x,y1,'r-')
plt.show()

#print len(sig)
sp = np.fft.fft(sig)
freq = np.fft.fftfreq(len(sig))*samp
plt.plot(freq, sp.real,'g-', freq, sp.imag,'b-')
plt.show()



#Wn=9600.0*2 / float(samp)
Wn=12e4 / float(samp)

#N= signal.buttord(Wn, Wn,3.0,16.0)
b, a =signal.butter(6, Wn, 'low')
lp1 = signal.lfilter(b, a, y1)
lp2 = signal.lfilter(b, a, y2)


pulse = map( lambda x: 6000 if x > 3000 else 0,lp1 )

print 1.0/Wn
# Manchester decode
obit = True
bits=[]
clock_level=True
clock_c=0
STATE_IDLE=0
STATE_RX=1
state=STATE_IDLE
clk=[]

P=samp/9600*2
print "Bitrate",
lastLevel =False
c=0
pol=True
#clk=0
#for s in pulse:
#  bit = s > 0
#  c = c + 1
#  if(bit ^ obit):
#    if(c > P*2):
#      print "Manchester violation"
#      clk=0#
#
#    if(c > P):
#      pol = not pol
#      clk = clk+2
#    else:
#      clk = clk+1
#
#    if((clk & 1)==1):
#      bits.append(pol) 
#
#
#    print c,P
#    c=0
#
#  obit=bit
  

T=0
for s in pulse:
  bit = s > 0;
  #Clock generator
  clock_c=clock_c +1

  if(clock_c>P):
     bits.append(bit) #sample manchester data
     print bit
     clock_c = clock_c-P
     clock_level = not clock_level

  T=T+1
  if(bit ^ obit):    
    #print clock_c,P,T
    T=0
    #Clock resync
    if(clock_c < P/2):
    	clock_c = 0
    else:
	clock_c =P/2

    #pi/2 phase shift
    clock_c = clock_c+P/4

  clk.append(4000 if clock_level else 0)    
  obit=bit



# Bits to bytes
c=0
by=0
bytes=""
for b in bits:
  by =  (by << 1) | b
  c = c +1
  if(c & 7 == 0):
  	bytes = bytes + chr(by)
  	by=0
bytes = bytes + chr(by)

print bytes.encode("hex")

p_corr = plt.plot(x, y1, 'r-',label="Correlated signal tone 1")
p_lowpadd = plt.plot(x, lp1, 'b-',label="Low pass filteres tone1")
p_lowpadd = plt.plot(x, lp2, 'm-',label="Low pass filteres tone2")
p_digital = plt.plot(x, pulse, 'g-',label="Digitalized low pass signal")
p_clock = plt.plot(clk, 'c-',label="Recoverd clock+pi/2")
plt.legend()
#plt.axis([0, 6, 0, 20])

#plt.legend([p_corr, p_lowpadd,p_digital,p_clock], ["", "","",""])
plt.show()
f.close()
