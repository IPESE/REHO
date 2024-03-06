
######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#--- Pumped Thermal Energy Storage unit
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
# -------------- Introduction ------------
# Composed of both a reservoir ("PTES_storage") and a conversion ("PTES_conversion") unit.
# It is able to store electricity and provides usable heat from conversion inefficiencies

#--------------- Test results ------------
# Time resolution example 1a with test constraints activated :
# Input =  0.0625
# Solve =  24.2188
# Output = 4
# 32728 variables:
# 	11 binary variables
# 	32717 linear variables
# 41733 constraints, all linear; 166026 nonzeros
# 	28042 equality constraints
# 	13691 inequality constraints
# Can't explain why is the "split" script which is performing better thant the "aggregated one"

# Example 3a time : Total (root+branch&cut) = 3000.86 sec. (2059405.61 ticks)
# Too long to be activated
# ----------- Parameters -----------
param PTES_efficiency{u in UnitsOfType['PTES_conversion']}>=0,<=1 := sqrt(0.67); #%
param PTES_self_discharge{u in UnitsOfType['PTES_storage']}>=0,<=1 default 0.01; #%/day

#PTES_heat_losses corresponds to non-usable heat
param PTES_heat_losses{u in UnitsOfType['PTES_conversion']}>=0,<=(1-PTES_efficiency[u]) default 0.0; #
# ------------ Variables -----------
var PTES_E_Stored{h in House, u in UnitsOfType['PTES_storage'] inter UnitsOfHouse[h], hy in Year} >= 0;	#kWh

var PTES_power_out_max {h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]} >=0;
var PTES_power_in_max {h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]} >=0;

# ------------ Constraints ----------

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
 = sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];#kWh;


#--Energy balance

subject to PTES_EB{h in House,us in UnitsOfType['PTES_storage'] inter UnitsOfHouse[h], uc in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h], hy in Year}:
(PTES_E_Stored[h,us,next(hy,Year)] - (1-PTES_self_discharge[us]/24)*PTES_E_Stored[h,us,hy]) = 
	( PTES_efficiency[uc]*Units_demand['Electricity',uc,PeriodOfYear[hy],TimeOfYear[hy]] - (1/PTES_efficiency[uc])*Units_supply['Electricity',uc,PeriodOfYear[hy],TimeOfYear[hy]] )*dt[PeriodOfYear[hy]];

# TEST 
# subject to PTES_c6{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]}:
# Units_Mult[u] >= 1;

# subject to PTES_c7{h in House, u in UnitsOfType['PTES_storage'] inter UnitsOfHouse[h]}:
# Units_Mult[u] >= 10;

# subject to PTES_c8{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]}:
# sum{p in Period, t in Time[p]} Units_supply['Electricity',u,p,t]>=50;