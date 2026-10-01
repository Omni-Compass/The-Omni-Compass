#pragma once
#include <array>
#include <string>
#include <vector>
namespace omnicompass {
inline constexpr double EPS=1e-12;
inline constexpr int MACRO_STEPS=20;
inline constexpr int MICRO_STEPS=10;
inline constexpr double MACRO_DT=0.1;
inline constexpr double MICRO_DT=0.01;
inline constexpr double BASIN_TOL=0.10;
inline constexpr int CONVEY_WINDOW=5;
inline constexpr int CERT_WINDOW=10;
inline constexpr double KP=12.0;
inline constexpr double U_AUTHORITY=25.0;
struct State { double E{},U{},I_U{},S{},B{},B_dot{}; };
struct Parameters {
 double alpha{},beta_int{},beta_ext{},k{},sigma_1{},delta{},gamma_1{},gamma_c{};
 double lambda_0{},lambda_1{},lambda_2{},c{},E_max{},omega_B{},Q_B{},alpha_s{},beta_s{};
 double mu{},alpha_E{},alpha_U{},lambda_I{},lambda_U{};
};
struct InputCase { int run_id{}; State initial{}; Parameters p{}; };
struct Result {
 int run_id{}; State final{}; std::array<double,21> U_hist{};
 int target_sign{}; int born{}; int convey{}; int convey_start{-1}; int convey_confirm{-1};
 int cert{}; int cert_start{-1}; int cert_complete{-1}; int max_streak{};
 double actuator_abs_integral{},actuator_sq_integral{},actuator_peak{}; int actuator_saturated_periods{};
};
int basin_sign(double U) noexcept;
int nearest_basin_sign(double U) noexcept;
double v_eff(const State&,const Parameters&,double t) noexcept;
State derivatives(const State&,const Parameters&,double t,double u_ctrl=0.0) noexcept;
State rk4_step(const State&,const Parameters&,double t,double dt,double u_hold) noexcept;
Result simulate(const InputCase&) noexcept;
std::vector<InputCase> read_inputs(const std::string& path);
void write_results(const std::string& path,const std::vector<Result>& rows);
}
