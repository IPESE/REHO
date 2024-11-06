#-First-order electrical storage model including:
#	1. dis-/charging efficiencies
#	2. self-discharging efficiency
#	3. dis-/charging limits
#-References :
# [1]	F. Oldewurtel et al., Building Control and Storage Management with [...], 2010
# [2]   M. Koller et al., Defining a Degradation Cost Function for Optimal [...], 2013

#-Adapted model to additionally include :
# [3] Efficiency degradation over time (efficiency used is an average of the CO2_stortery efficiency over its lifetime)
# [4] C-rate limitation (beware that maximum C-rate value is 1 (due to hourly resolution))

param CO2_stor_eff_charge{u in UnitsOfType['CO2storage']} 	default 1;	#- AC-AC efficiency
param CO2_stor_eff_discharge{u in UnitsOfType['CO2storage']} 	default 1;	#- AC-AC efficiency

param CO2_stor_limit_ch{u in UnitsOfType['CO2storage']} default 1;			#-	[2]
param CO2_stor_limit_di{u in UnitsOfType['CO2storage']} default 0;			#-	[1]

param C_rate_CO2{u in UnitsOfType['CO2storage']} default 1;					#-
param CO2_stor_self_discharge{u in UnitsOfType['CO2storage']} default 1;	#-	[1]

# param CO2_stor_RTE_degradation{u in UnitsOfType['CO2storage']} default 0.005; # CO2_stortery efficiency degradation per year
# param CO2_stor_efficiency{u in UnitsOfType['CO2storage']} >=0, <= sqrt(CO2_stor_eff_RTE_basis[u]) := sqrt(CO2_stor_eff_RTE_basis[u]-CO2_stor_RTE_degradation[u]*lifetime[u]/2); #Computation of the one way efficiency (assuming equal efficiency out and in)

var CO2_stor_charging{h in House, u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h], p in Period,t in Time[p]} >= 0;
var CO2_stor_discharging{h in House, u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h], p in Period,t in Time[p]} >= 0;
var CO2_stor_stored{h in House, u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h], hy in Year} >= 0;

var mode_charge_CO2{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]} binary;
var mode_discharge_CO2{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]} binary;
param M_stor_CO2 := 1e12;

subject to CO2_stor_charging_process{h in House,u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h], p in Period,t in Time[p]}:
	CO2_stor_charging[h,u,p,t] = CO2_stor_eff_charge[u]*Units_demand['CO2',u,p,t];

subject to CO2_stor_discharging_process{h in House,u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h], p in Period,t in Time[p]}:
	CO2_stor_discharging[h,u,p,t] = 1/CO2_stor_eff_discharge[u]*Units_supply['CO2',u,p,t];

#subject to CO2_stor_elec_use{h in House,u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h], p in Period,t in Time[p]}:
#	Units_demand['Electricity',u,p,t] = CO2_stor_charging[h,u,p,t] * 0.1;

#--Hourly Energy balance (valid for inter-period storage)
subject to CO2_stor_energy_balance{h in House,u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h], hy in Year}:
	CO2_stor_stored[h,u,next(hy,Year)] = CO2_stor_self_discharge[u]*CO2_stor_stored[h,u,hy] +
	(CO2_stor_charging[h,u,PeriodOfYear[hy],TimeOfYear[hy]] - CO2_stor_discharging[h,u,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];

#--SoC constraints
subject to CO2_stor_c1{h in House,u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h], hy in Year}:
	CO2_stor_stored[h,u,hy] <= CO2_stor_limit_ch[u]*Units_Mult[u];

subject to CO2_stor_c2{h in House,u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h], hy in Year}:
	CO2_stor_stored[h,u,hy] >= CO2_stor_limit_di[u]*Units_Mult[u];

#-- Power constraints
subject to CO2_stor_c3{h in House,u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h],p in PeriodStandard,t in Time[p]}:
	Units_demand['CO2',u,p,t]*dt[p] <= (CO2_stor_limit_ch[u]-CO2_stor_limit_di[u])*Units_Mult[u]*C_rate_CO2[u];

subject to CO2_stor_c4{h in House,u in UnitsOfType['CO2storage'] inter UnitsOfHouse[h],p in PeriodStandard,t in Time[p]}:
	Units_supply['CO2',u,p,t]*dt[p] <= (CO2_stor_limit_ch[u]-CO2_stor_limit_di[u])*Units_Mult[u]*C_rate_CO2[u];

# never charge and discharge storage simultaneously:
subject to is_stor_CO2_discharging{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]}:
    Units_supply['CO2',u,p,t] <= mode_discharge_CO2[u,p,t] * M_stor_CO2;

subject to is_stor_CO2_charging{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]}:
    Units_demand['CO2',u,p,t] <= mode_charge_CO2[u,p,t] * M_stor_CO2;

subject to no_charg_discharg_CO2{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]}:
    mode_discharge_CO2[u,p,t] + mode_charge_CO2[u,p,t] <= 1;