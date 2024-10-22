#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Methanizer
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param MTZ_conv_eff_basis{u in UnitsOfType['Methanizer']} >=0, <=1 default 0.78;
param MTZ_power_limit_in_basis{u in UnitsOfType['Methanizer']} >=0 default 1;
param MTZ_max_overall_efficiency{u in UnitsOfType['Methanizer']} >=0, <=1 default 1; 

var MTZ_Co2_needs{u in UnitsOfType['Methanizer'], p in Period, t in Time[p]} >=0;

subject to MTZ_co2_needs_computation{u in UnitsOfType['Methanizer'], p in Period, t in Time[p]}:
MTZ_Co2_needs[u,p,t] = 0.198*Units_demand['Hydrogen',u,p,t];

#-hot stream heat leaving 
subject to MTZ_Usable_heat_computation{h in House,u in UnitsOfType['Methanizer'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
Units_demand['Hydrogen',u,p,t]*(MTZ_max_overall_efficiency[u]-MTZ_conv_eff_basis[u]) = sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];;

subject to MTZ_energy_balance{u in UnitsOfType['Methanizer'], p in Period,t in Time[p]}:
Units_supply['Biogas',u,p,t] = MTZ_conv_eff_basis[u]*Units_demand['Hydrogen',u,p,t];

# Power limitation
subject to MTZ_PL_c1{u in UnitsOfType['Methanizer'], p in Period,t in Time[p]}:
Units_supply['Biogas',u,p,t] <= Units_Mult[u]*MTZ_power_limit_in_basis[u];
