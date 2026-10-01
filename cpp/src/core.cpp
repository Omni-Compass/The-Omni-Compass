#include "omnicompass/core.hpp"
#include <algorithm>
#include <cmath>
namespace omnicompass {
static State add_scaled(const State&a,const State&b,double s) noexcept{return {a.E+s*b.E,a.U+s*b.U,a.I_U+s*b.I_U,a.S+s*b.S,a.B+s*b.B,a.B_dot+s*b.B_dot};}
static State combine(const State&s,const State&k1,const State&k2,const State&k3,const State&k4,double h) noexcept{return {s.E+h*(k1.E+2*k2.E+2*k3.E+k4.E)/6.0,s.U+h*(k1.U+2*k2.U+2*k3.U+k4.U)/6.0,s.I_U+h*(k1.I_U+2*k2.I_U+2*k3.I_U+k4.I_U)/6.0,s.S+h*(k1.S+2*k2.S+2*k3.S+k4.S)/6.0,s.B+h*(k1.B+2*k2.B+2*k3.B+k4.B)/6.0,s.B_dot+h*(k1.B_dot+2*k2.B_dot+2*k3.B_dot+k4.B_dot)/6.0};}
int basin_sign(double U) noexcept {if(std::abs(U-1.0)<=BASIN_TOL)return 1;if(std::abs(U+1.0)<=BASIN_TOL)return -1;return 0;}
int nearest_basin_sign(double U) noexcept {return std::abs(U-1.0)<=std::abs(U+1.0)?1:-1;}
double v_eff(const State&s,const Parameters&p,double t) noexcept {double z=p.lambda_0+p.lambda_1*(s.U-0.5)+p.lambda_2*s.S;return std::cos(0.5*p.omega_B*t)*(p.c*std::tanh(z));}
State derivatives(const State&s,const Parameters&p,double t,double u) noexcept {
 double v=v_eff(s,p,t); double dE=-p.alpha_E*s.E+p.beta_int+p.beta_ext+v; double emax=std::max(p.E_max,1e-6);
 double dU=p.mu*s.U*(1.0-s.U*s.U)-dE/emax-p.lambda_U*s.U+u;
 double dI=(1.0-s.U)-p.sigma_1*s.E-p.delta*s.S-p.lambda_I*s.I_U;
 double dS=p.delta-p.alpha_s*s.S-0.75*p.beta_s*s.S*s.S;
 double dB=s.B_dot;
 double dBd=p.gamma_c*p.delta*s.S-(p.omega_B/std::max(p.Q_B,EPS))*s.B_dot-p.omega_B*p.omega_B*s.B;
 return {dE,dU,dI,dS,dB,dBd};
}
State rk4_step(const State&s,const Parameters&p,double t,double h,double u) noexcept {State k1=derivatives(s,p,t,u);State k2=derivatives(add_scaled(s,k1,0.5*h),p,t+0.5*h,u);State k3=derivatives(add_scaled(s,k2,0.5*h),p,t+0.5*h,u);State k4=derivatives(add_scaled(s,k3,h),p,t+h,u);return combine(s,k1,k2,k3,k4,h);}
Result simulate(const InputCase&in) noexcept {
 Result r{}; r.run_id=in.run_id; r.U_hist[0]=in.initial.U; r.target_sign=nearest_basin_sign(in.initial.U); r.born=basin_sign(in.initial.U)!=0;
 int sign0=basin_sign(in.initial.U), streak=r.born?1:0, streak_sign=r.born?sign0:0, cert_streak=streak, cert_sign=streak_sign; r.max_streak=streak;
 State s=in.initial; double t=0.0;
 for(int macro=1;macro<=MACRO_STEPS;++macro){
  for(int mi=0;mi<MICRO_STEPS;++mi){
   double drift=derivatives(s,in.p,t,0.0).U; double raw=-drift+KP*(double(r.target_sign)-s.U); double u=std::max(-U_AUTHORITY,std::min(U_AUTHORITY,raw));
   r.actuator_abs_integral+=std::abs(u)*MICRO_DT; r.actuator_sq_integral+=u*u*MICRO_DT; r.actuator_peak=std::max(r.actuator_peak,std::abs(u)); if(std::abs(raw)>U_AUTHORITY+EPS)++r.actuator_saturated_periods;
   s=rk4_step(s,in.p,t,MICRO_DT,u); t+=MICRO_DT;
  }
  r.U_hist[macro]=s.U; int bs=basin_sign(s.U); bool inside=bs!=0;
  if(inside){ if(bs==streak_sign)++streak; else{streak_sign=bs;streak=1;} } else {streak_sign=0;streak=0;}
  if(inside){ if(bs==cert_sign)++cert_streak; else{cert_sign=bs;cert_streak=1;} } else {cert_sign=0;cert_streak=0;}
  r.max_streak=std::max({r.max_streak,streak,cert_streak});
  if(!r.convey && streak>=CONVEY_WINDOW){r.convey=1;r.convey_start=macro-CONVEY_WINDOW+1;r.convey_confirm=macro;}
  if(!r.cert && cert_streak>=CERT_WINDOW){r.cert=1;r.cert_start=macro-CERT_WINDOW+1;r.cert_complete=macro;}
 }
 r.final=s; return r;
}
}
