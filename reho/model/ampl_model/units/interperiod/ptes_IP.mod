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
param PTES_self_discharge{u in UnitsOfType['PTES_storage']}>=0,<=1 default 0; #0.02; #%/day (half-life: 34 days)

#PTES_heat_losses corresponds to non-usable heat
#param PTES_heat_losses{u in UnitsOfType['PTES_conversion']}>= 0 default 0.2);

var PTES_E_Stored{u in UnitsOfType['PTES_storage'], hy in Year} >= 0;

var PTES_power_out_max {u in UnitsOfType['PTES_conversion']} >=0;
var PTES_power_in_max {u in UnitsOfType['PTES_conversion']} >=0;

# PTES_c1 set Units_Mult (it is an average of entering and leaving power)
subject to PTES_c1{u in UnitsOfType['PTES_conversion']}:
Units_Mult[u] >= (PTES_power_out_max[u]+PTES_power_in_max[u])/2;

subject to PTES_c2{u in UnitsOfType['PTES_conversion'], p in Period, t in Time[p]}:
Units_demand['Electricity',u,p,t]  <= PTES_power_in_max[u];

subject to PTES_c3{u in UnitsOfType['PTES_conversion'], p in Period, t in Time[p]}:
Units_supply['Electricity',u,p,t]  <= PTES_power_out_max[u];

subject to PTES_c4{u in UnitsOfType['PTES_storage'], hy in Year}:
PTES_E_Stored[u,hy] <= Units_Mult[u];


/*
#-hot stream heat leaving 
subject to PTES_Usable_heat_computation{u in UnitsOfType['PTES_conversion'],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
Units_demand['Electricity',u,p,t]*(1-PTES_efficiency[u]-PTES_heat_losses[u])
+ Units_supply['Electricity',u,p,t]*(1-PTES_efficiency[u]-PTES_heat_losses[u])
 >= sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];
*/

subject to PTES_EB{us in UnitsOfType['PTES_storage'], uc in UnitsOfType['PTES_conversion'], hy in Year}:
PTES_E_Stored[us,next(hy,Year)] = PTES_E_Stored[us,hy]*(1-PTES_self_discharge[us]/24) +
		(PTES_efficiency[uc]*Units_demand['Electricity',uc,PeriodOfYear[hy],TimeOfYear[hy]] -
		(1/PTES_efficiency[uc])* Units_supply['Electricity',uc,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];