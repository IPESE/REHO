#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Electrolyser
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param ETZ_conv_eff_basis{u in UnitsOfType['Electrolyzer']} >=0, <=1 default 0.76; # elec to H2 LHV eff : (H2 LHV/elec)
param ETZ_max_overall_efficiency{u in UnitsOfType['Electrolyzer']} >=0, <=1 default 1; # elec to H2 LHV eff : (H2 LHV/elec)
param ETZ_eff_degradation{u in UnitsOfType['Electrolyzer']} >=0, <= 1 default 0.12; #% losses per 1000h
param ETZ_power_limit_in_basis{u in UnitsOfType['Electrolyzer']} >=0 default 1;
param ETZ_conv_eff{u in UnitsOfType['Electrolyzer']} >=0, <=ETZ_max_overall_efficiency[u] := ETZ_conv_eff_basis[u]-ETZ_eff_degradation[u]*8760*lifetime[u]/2/1000/100;

#-hot stream heat leaving 
subject to ETZ_Usable_heat_computation{h in House,u in UnitsOfType['Electrolyzer'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
Units_demand['Electricity',u,p,t]*(ETZ_max_overall_efficiency[u]-ETZ_conv_eff[u]) = sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];;

subject to ETZ_energy_balance{u in UnitsOfType['Electrolyzer'], p in Period,t in Time[p]}:
Units_supply['Hydrogen',u,p,t] = ETZ_conv_eff[u]*Units_demand['Electricity',u,p,t];

# Power limitation
subject to ETZ_PL_c1{u in UnitsOfType['Electrolyzer'], p in Period,t in Time[p]}:
Units_demand['Electricity',u,p,t] <= Units_Mult[u]*ETZ_power_limit_in_basis[u];
