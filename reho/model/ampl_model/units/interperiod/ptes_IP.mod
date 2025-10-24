######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#  Pumped thermal energy storage
#
# References:
#	https://docs.nrel.gov/docs/fy20osti/76766.pdf
# 	https://www.sciencedirect.com/science/article/pii/S2352152X2201009X
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# Composed of both a reservoir ("PTES_storage") and a conversion ("PTES_conversion") unit.
# It is able to store electricity and provides usable heat from conversion inefficiencies

param PTES_efficiency{u in UnitsOfType['PTES_conversion']}>=0,<=1 := sqrt(0.67); #%
param PTES_self_discharge{u in UnitsOfType['PTES_storage']}>=0,<=1 default 0.02; #%/day (half-life: 34 days)

#PTES_heat_losses corresponds to non-usable heat
param PTES_heat_losses{u in UnitsOfType['PTES_conversion']}>=0,<=0.5*(1-PTES_efficiency[u]) default 0.0;

var PTES_E_Stored{h in House, u in UnitsOfType['PTES_storage'] inter UnitsOfHouse[h], hy in Year} >= 0;

var PTES_power_out_max {h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]} >=0;
var PTES_power_in_max {h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]} >=0;

# PTES_c1 set Units_Mult (it is an average of entering and leaving power)
subject to PTES_c1{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]}:
Units_Mult[u] >= (PTES_power_out_max[h,u]+PTES_power_in_max[h,u])/2;

subject to PTES_c2{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h], p in Period, t in Time[p]}:
Units_demand['Electricity',u,p,t]  <= PTES_power_in_max[h,u];

subject to PTES_c3{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h], p in Period, t in Time[p]}:
Units_supply['Electricity',u,p,t]  <= PTES_power_out_max[h,u];

subject to PTES_c4{h in House, u in UnitsOfType['PTES_storage'] inter UnitsOfHouse[h], hy in Year}:
PTES_E_Stored[h,u,hy] <= Units_Mult[u];

#-hot stream heat leaving 
subject to PTES_Usable_heat_computation{h in House,u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
Units_demand['Electricity',u,p,t]*(1-PTES_efficiency[u]-PTES_heat_losses[u])
+ Units_supply['Electricity',u,p,t]*(1-PTES_efficiency[u]-PTES_heat_losses[u])
 >= sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];

subject to PTES_EB{h in House,us in UnitsOfType['PTES_storage'] inter UnitsOfHouse[h], uc in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h], hy in Year}:
(PTES_E_Stored[h,us,next(hy,Year)] - (1-PTES_self_discharge[us]/24)*PTES_E_Stored[h,us,hy]) = 
	( PTES_efficiency[uc]*Units_demand['Electricity',uc,PeriodOfYear[hy],TimeOfYear[hy]] - (1/PTES_efficiency[uc])*Units_supply['Electricity',uc,PeriodOfYear[hy],TimeOfYear[hy]] )*dt[PeriodOfYear[hy]];
