#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# SOEFC
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# Can provide both H2 through SOEFC electrolysis and power through CH4 or H2 combustion

param SOEFC_conv_eff_basis{u in UnitsOfType['SOEFC']} >=0, <=1 default 0.77; # (elec output/H2 LHV) eff
param SOEFC_max_overall_efficiency{u in UnitsOfType['SOEFC']}>=0, <=1 default 1;
param SOEFC_power_limit_in{u in UnitsOfType['SOEFC']} >=0 default 1;
param SOEFC_power_limit_out{u in UnitsOfType['SOEFC']} >=0 default 0.6;
param SOEFC_eff_degradation{u in UnitsOfType['SOEFC']} >=0, <=1 default 0.005;#/1000H
param SOEFC_conv_eff{u in UnitsOfType['SOEFC']} >=0, <=SOEFC_conv_eff_basis[u] := SOEFC_conv_eff_basis[u]-SOEFC_eff_degradation[u]*8760*lifetime[u]/2/1000; # (elec output/H2 LHV) eff

subject to SOEFC_energy_balance{u in UnitsOfType['SOEFC'], p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] = SOEFC_conv_eff[u]*Units_demand['Hydrogen',u,p,t] + SOEFC_conv_eff[u]*Units_demand['Biogas',u,p,t];

subject to SOEFC_EB_c2{u in UnitsOfType['SOEFC'], p in Period,t in Time[p]}:
Units_supply['Hydrogen',u,p,t] = SOEFC_conv_eff[u]*Units_demand['Electricity',u,p,t];

#-hot stream heat leaving 
subject to SOEFC_Usable_heat_computation{h in House,u in UnitsOfType['SOEFC'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
Units_demand['Hydrogen',u,p,t]*(SOEFC_max_overall_efficiency[u]-SOEFC_conv_eff[u]) +
Units_demand['Biogas',u,p,t]*(SOEFC_max_overall_efficiency[u]-SOEFC_conv_eff[u]) +
Units_demand['Electricity',u,p,t]*(SOEFC_max_overall_efficiency[u]-SOEFC_conv_eff[u])
= sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];

# Power limitation
subject to SOEFC_PL_c1{u in UnitsOfType['SOEFC'],p in Period, t in Time[p]}:
Units_supply['Electricity',u,p,t] <= Units_Mult[u]*SOEFC_power_limit_out[u];

subject to SOEFC_PL_c2{u in UnitsOfType['SOEFC'],p in Period, t in Time[p]}:
Units_demand['Electricity',u,p,t] <= Units_Mult[u]*SOEFC_power_limit_in[u];
