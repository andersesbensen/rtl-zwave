#include<stdio.h>
#include<complex>

double sr = 2.028e6;
using namespace std;
/*
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
 */
double
fsk_demodulator(char re, char im)
{
  static complex<double> s1=0, s2=0;
  double r;
  complex<double> s((double) re, (double) im);

  double a2 = norm(s);

  if (a2 > 0.0)
    {
      complex<double> ds = (s - s2) / 2.0; // the derivative
      r = -imag( (conj(s1) * ds) / a2);
    }
  else
    {
      r = 0.0;
    }
  s2 = s1; // save 2 samp behind
  s1 = s;

  return r;
}

/**
 * Lowpass filter butterworth order 6 cutoff 120khz
 */
static double
freq_filter(double in)
{
#define NZEROS1 6
#define NPOLES1 6
#define GAIN1   4.914064842e+04
  static double xv[NZEROS1 + 1], yv[NPOLES1 + 1];
    {
      xv[0] = xv[1];
      xv[1] = xv[2];
      xv[2] = xv[3];
      xv[3] = xv[4];
      xv[4] = xv[5];
      xv[5] = xv[6];
      xv[6] = in / GAIN1;
      yv[0] = yv[1];
      yv[1] = yv[2];
      yv[2] = yv[3];
      yv[3] = yv[4];
      yv[4] = yv[5];
      yv[5] = yv[6];
      yv[6] = (xv[0] + xv[6]) + 6 * (xv[1] + xv[5]) + 15 * (xv[2] + xv[4])
          + 20 * xv[3] + (-0.2386551347 * yv[0]) + (1.7710414118 * yv[1])
          + (-5.5245979401 * yv[2]) + (9.2819800973 * yv[3])
          + (-8.8701476352 * yv[4]) + (4.5790768167 * yv[5]);
      return yv[6];
    }
}

/* Digital filter designed by mkfilter/mkshape/gencode   A.J. Fisher
 Command line: /www/usr/fisher/helpers/mkfilter -Bu -Lp -o 6 -a 5.8593750000e-03 0.0000000000e+00 -l */
static double
lock_filter(double in)
{
#define NZEROS2 3
#define NPOLES2 3
#define GAIN2   1.662796182e+05

static float xv[NZEROS2+1], yv[NPOLES2+1];

      { xv[0] = xv[1]; xv[1] = xv[2]; xv[2] = xv[3];
        xv[3] = in / GAIN2;
        yv[0] = yv[1]; yv[1] = yv[2]; yv[2] = yv[3];
        yv[3] =   (xv[0] + xv[3]) + 3 * (xv[1] + xv[2])
                     + (  0.9290105002 * yv[0]) + ( -2.8554316873 * yv[1])
                     + (  2.9263730753 * yv[2]);
        return yv[3];
      }
}

int
main()
{
  float f, s, lock;

  enum
  {
    S_IDLE, S_PREAMP, S_BITLOCK
  } state = S_IDLE;
  enum
  {
    B_PREAMP, B_SOF0, B_SOF1, B_DATA
  } state_b;

  int pre_len = 0; //  # Length of preamble bit
  int pre_cnt = 0;
  int bit_len = 0;
  float bit_cnt = 0.0;
  float wc = 0; //  # center frequency
  bool last_logic = false;
  const int lead_in = 10;

  bool last_bit;
  int b_cnt;
  while (!feof(stdin))
    {
      f = fsk_demodulator(getc(stdin) - 127, getc(stdin) - 127);
      s = freq_filter(f);
      lock = lock_filter(f);

      printf("%e %e %e\n",f,s,lock);

      bool logic = (s - wc) > 0;
      if (lock < 0.0)
        {    //DO this does not hold...

          if (state == S_IDLE)
            {
              state = S_PREAMP;
              pre_cnt = 0;
              pre_len = 0;
            }
          else if (state == S_PREAMP)
            {
              wc = lock;
              pre_len = pre_len + 1;
              if (logic ^ last_logic)
                { //#edge trigger (rising and falling)
                  pre_cnt = pre_cnt + 1;
                }

              if (pre_cnt == lead_in)
                {  //# skip the first lead_in
                  pre_len = 0;
                }
              else if (pre_cnt > 30)
                {
                  state = S_BITLOCK;
                  state_b = B_PREAMP;

                  bit_len = float(pre_len) / (pre_cnt - lead_in);
                  bit_cnt = bit_len / 2.0;
                  last_bit = not logic;
                }
              else if (state == S_BITLOCK)
                {
                  if (logic ^ last_logic)
                    {
                      bit_cnt = bit_len / 2.0; //#Re-sync on edges
                    }
                  else
                    {
                      bit_cnt = bit_cnt + 1.0;
                    }

                  if (bit_cnt >= bit_len)
                    { // # new bit
                      if (state_b == B_PREAMP)
                        {
                          if (logic and last_bit)
                            {
                              state_b = B_SOF1;
                              b_cnt = 1; //This was the first SOF bit
                            }
                        }
                      else if (state_b == B_SOF0)
                        {
                          if (not logic)
                            {
                              b_cnt = b_cnt + 1;
                              if (b_cnt == 4)
                                {
                                  b_cnt = 0;
                                  state_b = B_DATA;
                                }
                            }
                          else
                            {
                              printf("SOF0 error \n");
                              state = S_IDLE;
                            }
                        }
                      else if (state_b == B_SOF1)
                        {
                          if (logic)
                            {
                              b_cnt = b_cnt + 1;
                              if (b_cnt == 4)
                                {
                                  b_cnt = 0;
                                  state_b = B_SOF0;
                                }
                            }
                          else
                            {
                              printf("SOF1 error \n");
                              state = S_IDLE;
                            }
                        }
                      else if (state_b == B_DATA)
                        {
                          printf("%1i", logic);
                        }
                    }
                  bit_cnt = bit_cnt - bit_len;
                }
              else
                { //# No LOCKs
                  if (state == S_BITLOCK)
                    {
                      printf("\n");
                      //frame = bits2bytes(bits)
                      //zwave_print(frame)
                    }
                  state = S_IDLE;
                }
              last_logic = logic;
            }
        }
    }
  return 0;
}
