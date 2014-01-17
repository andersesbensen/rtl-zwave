#include<stdio.h>
#include<complex>


using namespace std;

extern void write_wiresark(unsigned char *f, unsigned char len,int speed);
extern int open_wirreshark();


void zwave_print(unsigned char* data, int len) {

	for(int i=0; i < len; i++) {
		printf("%.2x",data[i]);
	}
	printf("\n");
}


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


 this function returns the angular frequency of the current QI sample.
 To get the actual frequency
 f = w* (sr / 2*pi)
 where sr is the sample rate
 */
static inline double fsk_demodulator(int re, int im) {
	static complex<double> s1 = 0;
	static complex<double> s2 = 0;
	double w;
	complex<double> s((double) re, (double) im);

	double a2 = norm(s1);

	if (a2 > 0.0) {
		complex<double> ds = (s - s2) / 2.0; // the derivative
		complex<double> q = conj(s1) * ds;
		w = -imag(q) / a2;
	} else {
		w = 0.0;
	}
	s2 = s1; // save 2 samp behind
	s1 = s;

	return w;
}

/**
 * Lowpass filter butterworth order 6 cutoff 120khz
 */
static inline double freq_filter(double in) {
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

/*
 * Butterworth oder 3 low pass cutoff 12khz
 * Digital filter designed by mkfilter/mkshape/gencode   A.J. Fisher
 Command line: /www/usr/fisher/helpers/mkfilter -Bu -Lp -o 6 -a 5.8593750000e-03 0.0000000000e+00 -l */
static inline  double lock_filter(double in) {
#define NZEROS2 3
#define NPOLES2 3
#define GAIN2   1.662796182e+05

	static float xv[NZEROS2 + 1], yv[NPOLES2 + 1];

	{
		xv[0] = xv[1];
		xv[1] = xv[2];
		xv[2] = xv[3];
		xv[3] = in / GAIN2;
		yv[0] = yv[1];
		yv[1] = yv[2];
		yv[2] = yv[3];
		yv[3] = (xv[0] + xv[3]) + 3 * (xv[1] + xv[2]) + (0.9290105002 * yv[0])
				+ (-2.8554316873 * yv[1]) + (2.9263730753 * yv[2]);
		return yv[3];
	}
}

struct frame_state {
	unsigned int  bit_count;
	unsigned int  data_len;
	unsigned char data[64];

	bool last_bit;

	int b_cnt;

	enum {
		B_PREAMP, B_SOF0, B_SOF1, B_DATA
	} state_b;
} fs;



enum {
	S_IDLE, S_PREAMP, S_BITLOCK
} state = S_IDLE;

int pre_len = 0; //  # Length of preamble bit
int pre_cnt = 0;
double bit_len = 0;
double bit_cnt = 0.0;
double wc = 0; //  # center frequency
bool last_logic = false;
const int lead_in = 10;


int main() {
	double f, s, lock;


	open_wirreshark();


	while (!feof(stdin)) {
		unsigned char g[2];
		fread(g, 2, 1, stdin);
		f = fsk_demodulator(g[0] - 127, g[1] - 127);

		s = freq_filter(f);

		/*
		 * We use a 12khz lowpass filter to lock on to a preable. When this value is "stable",
		 * a preamble could be present, further more the value of lock, will correspond to the
		 * center frequency of the fsk (wc)
		 */
		lock = lock_filter(f);

		//printf("%e %e %e\n",f,s,lock);

		/* TODO come up with a better lock detection
		 * just using lock < 0 as lock condition, seems rather arbitrary
		 */
		if (lock < 0.0) {
			bool logic = (s - wc) > 0;

			if (state == S_IDLE) {
				state = S_PREAMP;
				pre_cnt = 0;
				pre_len = 0;
			} else if (state == S_PREAMP) {
				wc = lock;
				pre_len = pre_len + 1;
				if (logic ^ last_logic) { //#edge trigger (rising and falling)
					pre_cnt = pre_cnt + 1;

					if (pre_cnt == lead_in) {  //# skip the first lead_in
						pre_len = 0;
					} else if (pre_cnt > 30) {
						state = S_BITLOCK;
						fs.state_b = fs.B_PREAMP;
						fs.last_bit = not logic;

						bit_len = double(pre_len) / (pre_cnt - lead_in);
						bit_cnt = bit_len / 2.0;
					}
				}
			} else if (state == S_BITLOCK) {
				if (logic ^ last_logic) {
					bit_cnt = bit_len / 2.0; //#Re-sync on edges
				} else {
					bit_cnt = bit_cnt + 1.0;
				}
				if (bit_cnt >= bit_len) { // # new bit
					//Sub statemachine
					if (fs.state_b == fs.B_PREAMP) {
						if (logic and fs.last_bit) {
							fs.state_b = fs.B_SOF1;
							fs.b_cnt = 1; //This was the first SOF bit
						}
					} else if (fs.state_b == fs.B_SOF0) {
						if (not logic) {
							if (fs.b_cnt == 4) {
								fs.b_cnt = 0;
								fs.data_len = 0;
								fs.state_b = fs.B_DATA;
							}
						} else {
							//printf("SOF0 error \n");
							state = S_IDLE;
						}
					} else if (fs.state_b == fs.B_SOF1) {
						if (logic) {
							if (fs.b_cnt == 4) {
								fs.b_cnt = 0;
								fs.state_b = fs.B_SOF0;
							}
						} else {
							//printf("SOF1 error \n");
							state = S_IDLE;
						}
					} else if (fs.state_b == fs.B_DATA) { //Payload bit
						fs.data[fs.data_len] = (fs.data[fs.data_len] << 1) | logic;
						if( (fs.b_cnt & 7) == 0) {
							fs.data[++fs.data_len] = 0;
						}
					}
					fs.last_bit = logic;
					fs.b_cnt++;
					bit_cnt = bit_cnt - bit_len;
				}
			}
			last_logic = logic;
		}
		else { //# No LOCKs
			if (state == S_BITLOCK && fs.state_b == fs.B_DATA) {
				//zwave_print(fs.data,fs.data_len);
				write_wiresark(fs.data,fs.data_len, bit_len < 30 ? 2 : 1 );
				//frame = bits2bytes(bits)
				//zwave_print(frame)
			}
			state = S_IDLE;
		}
	}
	return 0;
}
