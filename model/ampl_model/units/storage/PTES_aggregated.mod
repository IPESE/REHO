#Time resolution example 1a with test constraints activated : 
# Input =  0.0625
# Solve =  38.4688
# Output = 3.10938
# 32727 variables:
# 	10 binary variables
# 	32717 linear variables
# 41732 constraints, all linear; 166023 nonzeros
# 	28041 equality constraints
# 	13691 inequality constraints

# ----------- Parameters -----------
param PTES_efficiency{u in UnitsOfType['PTES_conversion']}>=0,<=1 := sqrt(0.67); #%
param PTES_self_discharge{u in UnitsOfType['PTES_conversion']}>=0,<=1 default 0.01; #%/day

param PTES_heat_losses{u in UnitsOfType['PTES_conversion']}>=0,<=(1-PTES_efficiency[u]) default 0.0; #
# ------------ Variables -----------
var PTES_E_Stored{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h], hy in Year} >= 0;	#kWh

var PTES_power_out_max {h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]} >=0;
var PTES_power_in_max {h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]} >=0;

var PTES_S_Size{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]}>=0;
var Units_Mult_Power{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]}>=0;

# ------------ Constraints ----------

# PTES_c1 set Units_Mult
subject to PTES_c1{h in House,u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]}:
Units_Mult[u] >= 574*Units_Mult_Power[h,u] + PTES_S_Size[h,u]*17;

subject to PTES_c2{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h], p in Period, t in Time[p]}:
Units_demand['Electricity',u,p,t]  <= PTES_power_in_max[h,u];

subject to PTES_c3{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h], p in Period, t in Time[p]}:
Units_supply['Electricity',u,p,t]  <= PTES_power_out_max[h,u];

subject to PTES_c4{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h], hy in Year}:
PTES_E_Stored[h,u,hy] <= PTES_S_Size[h,u];

subject to PTES_c5{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]}:
(PTES_power_in_max[h,u]+PTES_power_out_max[h,u])/2 <= Units_Mult_Power[h,u];

#-hot stream heat leaving 
subject to PTES_Usable_heat_computation{h in House,u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
Units_demand['Electricity',u,p,t]*(1-PTES_efficiency[u]-PTES_heat_losses[u])
+ Units_supply['Electricity',u,p,t]*(1-PTES_efficiency[u]-PTES_heat_losses[u])
 = sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];#kWh;


#--Energy balance
subject to PTES_EB{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h], hy in Year}:
(PTES_E_Stored[h,u,next(hy,Year)] - (1-PTES_self_discharge[u]/24)*PTES_E_Stored[h,u,hy]) = 
	( PTES_efficiency[u]*Units_demand['Electricity',u,PeriodOfYear[hy],TimeOfYear[hy]] - (1/PTES_efficiency[u])*Units_supply['Electricity',u,PeriodOfYear[hy],TimeOfYear[hy]] )*dt[PeriodOfYear[hy]];	#kWh

# TEST 
# subject to PTES_c6{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]}:
# Units_Mult_Power[h,u] >= 1;

# subject to PTES_c7{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]}:
# PTES_S_Size[h,u] >= 10;

# subject to PTES_c8{h in House, u in UnitsOfType['PTES_conversion'] inter UnitsOfHouse[h]}:
# sum{p in Period, t in Time[p]} Units_supply['Electricity',u,p,t]>=50;