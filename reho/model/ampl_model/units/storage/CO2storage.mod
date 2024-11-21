#-First-order electrical storage model including:
#	1. dis-/charging efficiencies
#	2. self-discharging efficiency
#	3. dis-/charging limits
#-References :


param CO2_stor_eff_charge{u in UnitsOfType['CO2storage']} 	default 1;	#- AC-AC efficiency
param CO2_stor_eff_discharge{u in UnitsOfType['CO2storage']} 	default 1;	#- AC-AC efficiency

param CO2_stor_limit_ch{u in UnitsOfType['CO2storage']} default 1;			#-	[2]
param CO2_stor_limit_di{u in UnitsOfType['CO2storage']} default 0;			#-	[1]

param C_rate_CO2{u in UnitsOfType['CO2storage']} default 0.01;					#-
param CO2_stor_self_discharge{u in UnitsOfType['CO2storage']} default 1;	#-	[1]
param CO2_stor_elec_eff{u in UnitsOfType['CO2storage']} default 0.02; #at medium pressure (75 bars)

var CO2_stor_charging{u in UnitsOfType['CO2storage'], p in Period,t in Time[p]} >= 0;
var CO2_stor_discharging{u in UnitsOfType['CO2storage'], p in Period,t in Time[p]} >= 0;
var CO2_stor_stored{u in UnitsOfType['CO2storage'], hy in Year} >= 0;

var mode_charge_CO2{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]} binary := 0;
var mode_discharge_CO2{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]} binary := 0;
param M_stor_CO2 := 1e7;

subject to CO2_stor_charging_process{u in UnitsOfType['CO2storage'], p in Period,t in Time[p]}:
	CO2_stor_charging[u,p,t] = CO2_stor_eff_charge[u]*Units_demand['CO2',u,p,t];

subject to CO2_stor_discharging_process{u in UnitsOfType['CO2storage'], p in Period,t in Time[p]}:
	CO2_stor_discharging[u,p,t] = 1/CO2_stor_eff_discharge[u]*Units_supply['CO2',u,p,t];

subject to CO2_stor_elec_use{u in UnitsOfType['CO2storage'], p in Period,t in Time[p]}:
	Units_demand['Electricity',u,p,t] = CO2_stor_charging[u,p,t] * CO2_stor_elec_eff[u];

#--Hourly Energy balance (valid for inter-period storage)
subject to CO2_stor_energy_balance{u in UnitsOfType['CO2storage'], hy in Year}:
	CO2_stor_stored[u,next(hy,Year)] = CO2_stor_self_discharge[u]*CO2_stor_stored[u,hy] +
	(CO2_stor_charging[u,PeriodOfYear[hy],TimeOfYear[hy]] - CO2_stor_discharging[u,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];

#--SoC constraints
subject to CO2_stor_c1{u in UnitsOfType['CO2storage'], hy in Year}:
	CO2_stor_stored[u,hy] <= CO2_stor_limit_ch[u]*Units_Mult[u];

subject to CO2_stor_c2{u in UnitsOfType['CO2storage'], hy in Year}:
	CO2_stor_stored[u,hy] >= CO2_stor_limit_di[u]*Units_Mult[u];

#-- Power constraints
subject to CO2_stor_c3{u in UnitsOfType['CO2storage'],p in PeriodStandard,t in Time[p]}:
	Units_demand['CO2',u,p,t]*dt[p] <= (CO2_stor_limit_ch[u]-CO2_stor_limit_di[u])*Units_Mult[u]*C_rate_CO2[u];

subject to CO2_stor_c4{u in UnitsOfType['CO2storage'],p in PeriodStandard,t in Time[p]}:
	Units_supply['CO2',u,p,t]*dt[p] <= (CO2_stor_limit_ch[u]-CO2_stor_limit_di[u])*Units_Mult[u]*C_rate_CO2[u];

# never charge and discharge storage simultaneously:
subject to is_stor_CO2_discharging{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]}:
    Units_supply['CO2',u,p,t] <= mode_discharge_CO2[u,p,t] * M_stor_CO2;

subject to is_stor_CO2_charging{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]}:
    Units_demand['CO2',u,p,t] <= mode_charge_CO2[u,p,t] * M_stor_CO2;

subject to no_charg_discharg_CO2{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]}:
    mode_discharge_CO2[u,p,t] + mode_charge_CO2[u,p,t] <= 1;