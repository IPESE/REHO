#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---FUEL CELL MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
# ----------------------------------------- PARAMETERS ---------------------------------------
param FC_conv_el_eff_basis{u in UnitsOfType['FuelCell']} default 0.65; # (elec output/H2 LHV) eff
param FC_power_limit_in_basis{u in UnitsOfType['FuelCell']} >=0 default 1; #kW/kWn
param FC_eff_yearly_degradation{u in UnitsOfType['FuelCell']} default 0.0175;
param FC_max_overall_efficiency{u in UnitsOfType['FuelCell']} default 1; #elec + thermal efficiency 

param FC_conv_eff{u in UnitsOfType['FuelCell']} >=0, <=FC_max_overall_efficiency[u] := FC_conv_el_eff_basis[u]-FC_eff_yearly_degradation[u]*lifetime[u]/2; 

# ----------------------------------------- VARIABLES ---------------------------------------


# ---------------------------------------- CONSTRAINTS ---------------------------------------

#--Energy balance

subject to FC_EB_c1{u in UnitsOfType['FuelCell'], p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] = FC_conv_eff[u]*Units_demand['Hydrogen',u,p,t]; #kW

#-hot stream heat leaving 
# the efficiency degradation is assumed to be usable as heat (as it mostly occurs in the FC reactor)
subject to FC_Usable_heat_computation{h in House,u in UnitsOfType['FuelCell'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
Units_demand['Hydrogen',u,p,t]*(FC_max_overall_efficiency[u]-FC_conv_eff[u]) = sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];#kWh;


# Power limitation
subject to FC_PL_c1{u in UnitsOfType['FuelCell'],p in Period, t in Time[p]}:
Units_supply['Electricity',u,p,t] <= Units_Mult[u]*FC_power_limit_in_basis[u]; #kW

