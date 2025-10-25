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

param PTES_efficiency{uc in UnitsOfType['PTES_conversion']}>=0,<=1 := sqrt(0.67); #%
param PTES_self_discharge{us in UnitsOfType['PTES_storage']}>=0,<=1 default 0.1; # %/day (half-life: 34 days)
param PTES_COP{us in UnitsOfType['PTES_conversion']}>=0 default 3.5;
#PTES_heat_losses corresponds to non-usable heat
param PTES_heat_losses{uc in UnitsOfType['PTES_conversion']}>= 0 default 0.2;

var PTES_E_Stored{us in UnitsOfType['PTES_storage'], hy in Year} >= 0;

var PTES_power_out_max {uc in UnitsOfType['PTES_conversion']} >=0;
var PTES_power_in_max {uc in UnitsOfType['PTES_conversion']} >=0;

# PTES_c1 set Units_Mult (it is an average of entering and leaving power)
subject to PTES_c1{uc in UnitsOfType['PTES_conversion']}:
Units_Mult[uc] >= (PTES_power_out_max[uc]+PTES_power_in_max[uc])/2;

subject to PTES_c2{uc in UnitsOfType['PTES_conversion'], p in Period, t in Time[p]}:
Units_demand['Electricity',uc,p,t]  <= PTES_power_in_max[uc];

subject to PTES_c3{uc in UnitsOfType['PTES_conversion'], p in Period, t in Time[p]}:
Units_supply['Electricity',uc,p,t]  <= PTES_power_out_max[uc];

subject to PTES_c4{us in UnitsOfType['PTES_storage'], uc in UnitsOfType['PTES_conversion'], hy in Year}:
PTES_E_Stored[us,hy]*PTES_COP[uc] <= Units_Mult[us];

/*
#-hot stream heat leaving 
subject to PTES_Usable_heat_computation{uc in UnitsOfType['PTES_conversion'],st in StreamsOfUnit[uc],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
Units_demand['Electricity',uc,p,t]*(1-PTES_efficiency[uc]-PTES_heat_losses[uc])
+ Units_supply['Electricity',uc,p,t]*(1-PTES_efficiency[uc]-PTES_heat_losses[uc])
 >= sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];

*/

subject to PTES_EB{us in UnitsOfType['PTES_storage'], uc in UnitsOfType['PTES_conversion'], hy in Year}:
PTES_E_Stored[us,next(hy,Year)] = PTES_E_Stored[us,hy]*(1-PTES_self_discharge[us]/24) +
		(PTES_efficiency[uc]*Units_demand['Electricity',uc,PeriodOfYear[hy],TimeOfYear[hy]] -
		(1/PTES_efficiency[uc])* Units_supply['Electricity',uc,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];
#--------------------------------------------------------------------------------------------------------------------#
#  PTES charge/discharge mutual exclusivity
#--------------------------------------------------------------------------------------------------------------------#

param M_PTES default 1e6;   # Big-M parameter (should exceed maximum expected power in kW)

var mode_charge_PTES{uc in UnitsOfType['PTES_conversion'], p in Period, t in Time[p]} binary;
var mode_discharge_PTES{uc in UnitsOfType['PTES_conversion'], p in Period, t in Time[p]} binary;

# Prevent simultaneous charge and discharge
subject to is_PTES_charging{uc in UnitsOfType['PTES_conversion'], p in Period, t in Time[p]}:
    Units_demand['Electricity', uc, p, t] <= mode_charge_PTES[uc, p, t] * M_PTES;

subject to is_PTES_discharging{uc in UnitsOfType['PTES_conversion'], p in Period, t in Time[p]}:
    Units_supply['Electricity', uc, p, t] <= mode_discharge_PTES[uc, p, t] * M_PTES;

subject to no_charg_discharg_PTES{uc in UnitsOfType['PTES_conversion'], p in Period, t in Time[p]}:
    mode_charge_PTES[uc, p, t] + mode_discharge_PTES[uc, p, t] <= 1;

subject to PTES_elec_through_conv_unit_only_1{us in UnitsOfType['PTES_storage'], p in Period, t in Time[p]}:
Units_demand['Electricity', us, p, t] = 0;

subject to PTES_elec_through_conv_unit_only_2{us in UnitsOfType['PTES_storage'], p in Period, t in Time[p]}:
Units_supply['Electricity', us, p, t] = 0;