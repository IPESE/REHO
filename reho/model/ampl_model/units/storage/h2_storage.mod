#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Hydrogen storage tank
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param H2S_Elec_compression_needs_ratio{u in UnitsOfType['H2compression']} >=0, <=1 default 0.12; #Compressions electrical losses as H2 consumption
param H2S_expansion_efficiency{u in UnitsOfType['H2compression']} >=0, <=1 := 0.93;
param H2S_compression_efficiency{u in UnitsOfType['H2compression']} >=0, <=1 := 0.85;
param H2S_compression_usable_heat_share{u in UnitsOfType['H2compression']} >=0, <=H2S_Elec_compression_needs_ratio[u] := H2S_Elec_compression_needs_ratio[u]*(1-H2S_compression_efficiency[u]);
param H2S_expansion_usable_heat_share{u in UnitsOfType['H2compression']} >=0, <=H2S_Elec_compression_needs_ratio[u]-H2S_compression_usable_heat_share[u] 
	:= (H2S_Elec_compression_needs_ratio[u]-H2S_compression_usable_heat_share[u])*(1-H2S_expansion_efficiency[u]);
param H2S_compression_heat_loss{u in UnitsOfType['H2compression']} >=0, <=H2S_compression_usable_heat_share[u] := 0.0;
param H2S_expansion_heat_loss{u in UnitsOfType['H2compression']} >=0, <=H2S_expansion_usable_heat_share[u] := 0.0;

var H2S_E_stored{h in House,u in UnitsOfType['H2storage'], hy in Year} >= 0;
var H2S_compression_power_max{h in House,u in UnitsOfType['H2compression']}>=0;
var H2S_expansion_power_max{h in House,u in UnitsOfType['H2compression']}>=0;

subject to H2S_EB_c2{h in House,u in UnitsOfType['H2storage'], up in UnitsOfType['H2compression'], hy in Year}:
(H2S_E_stored[h,u,next(hy,Year)]-H2S_E_stored[h,u,hy]) = 
	(Units_demand['Hydrogen',up,PeriodOfYear[hy],TimeOfYear[hy]] - Units_supply['Hydrogen',up,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];

subject to H2S_EB_c3{h in House,u in UnitsOfType['H2compression'], p in Period,t in Time[p]}:
Units_demand['Electricity',u,p,t] = Units_demand['Hydrogen',u,p,t]*H2S_Elec_compression_needs_ratio[u];

subject to H2S_EB_c4{h in House,u in UnitsOfType['H2compression'], p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] = Units_supply['Hydrogen',u,p,t]*(H2S_Elec_compression_needs_ratio[u]-H2S_compression_usable_heat_share[u]-H2S_expansion_usable_heat_share[u]);

#-hot stream heat leaving 
subject to H2S_Usable_heat_computation{h in House,u in UnitsOfType['H2compression'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
Units_demand['Electricity',u,p,t]*(H2S_compression_usable_heat_share[u]-H2S_compression_heat_loss[u])
+ Units_supply['Electricity',u,p,t]*(H2S_expansion_usable_heat_share[u]-H2S_expansion_heat_loss[u])
= sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];

#--SoC constraints
subject to H2S_c1{h in House,u in UnitsOfType['H2storage'], hy in Year}:
H2S_E_stored[h,u,hy] <= Units_Mult[u];

#-- Power limit
subject to H2S_EB_c5{h in House,u in UnitsOfType['H2compression'], p in Period,t in Time[p]}:
Units_demand['Electricity',u,p,t] <= H2S_compression_power_max[h,u];

subject to H2S_EB_c6{h in House,u in UnitsOfType['H2compression'], p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] <= H2S_expansion_power_max[h,u];

subject to H2S_EB_c7{h in House,u in UnitsOfType['H2compression']}:
Units_Mult[u] >= (H2S_expansion_power_max[h,u]+ H2S_compression_power_max[h,u])/2;
