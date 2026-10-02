// SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
// Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
// Omni-Compass Enterprise License. See LICENSE.
#include "omnicompass/core.hpp"
#include <iostream>
int main(int argc,char**argv){if(argc!=3){std::cerr<<"usage: oc_run_fixture INPUT.csv OUTPUT.csv\n";return 2;}try{auto in=omnicompass::read_inputs(argv[1]);std::vector<omnicompass::Result>out;out.reserve(in.size());for(auto&x:in)out.push_back(omnicompass::simulate(x));omnicompass::write_results(argv[2],out);std::cout<<"processed "<<out.size()<<" current-engine fixtures\n";return 0;}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
