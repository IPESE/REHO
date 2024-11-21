#-First-order electrical storage model including:
#	1. dis-/charging efficiencies
#	2. self-discharging efficiency
#	3. dis-/charging limits
#-References :

param CH4_stor_eff_charge{u in UnitsOfType['CH4storage']} 	default 1;	#- AC-AC efficiency
param CH4_stor_eff_discharge{u in UnitsOfType['CH4storage']} 	default 1;	#- AC-AC efficiency

param CH4_stor_limit_ch{u in UnitsOfType['CH4storage']} default 1;			#-	[2]
param CH4_stor_limit_di{u in UnitsOfType['CH4storage']} default 0;			#-	[1]

param C_rate_CH4{u in UnitsOfType['CH4storage']} default 0.01;					#-
param CH4_stor_self_discharge{u in UnitsOfType['CH4storage']} default 1;	#-	[1]
param CH4_stor_elec_eff{u in UnitsOfType['CH4storage']} default 0.02; #at medium pressure (75 bars)

var CH4_stor_charging{u in UnitsOfType['CH4storage'], p in Period,t in Time[p]} >= 0;
var CH4_stor_discharging{u in UnitsOfType['CH4storage'], p in Period,t in Time[p]} >= 0;
var CH4_stor_stored{u in UnitsOfType['CH4storage'], hy in Year} >= 0;

var mode_charge_CH4{u in UnitsOfType['CH4storage'], p in Period, t in Time[p]} binary := 0;
var mode_discharge_CH4{u in UnitsOfType['CH4storage'], p in Period, t in Time[p]} binary := 0;
param M_stor_CH4 := 1e6;

subject to CH4_stor_charging_process{u in UnitsOfType['CH4storage'], p in Period,t in Time[p]}:
	CH4_stor_charging[u,p,t] = CH4_stor_eff_charge[u]*Units_demand['Biomethane',u,p,t];

subject to CH4_stor_discharging_process{u in UnitsOfType['CH4storage'], p in Period,t in Time[p]}:
	CH4_stor_discharging[u,p,t] = 1/CH4_stor_eff_discharge[u]*Units_supply['Biomethane',u,p,t];

subject to CH4_stor_elec_use{u in UnitsOfType['CH4storage'], p in Period,t in Time[p]}:
	Units_demand['Electricity',u,p,t] = Units_demand['Biomethane',u,p,t] * CH4_stor_elec_eff[u];

#--Hourly Energy balance (valid for inter-period storage)
subject to CH4_stor_energy_balance{u in UnitsOfType['CH4storage'], hy in Year}:
	CH4_stor_stored[u,next(hy,Year)] = CH4_stor_self_discharge[u]*CH4_stor_stored[u,hy] +
	(CH4_stor_charging[u,PeriodOfYear[hy],TimeOfYear[hy]] - CH4_stor_discharging[u,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];

#--SoC constraints
subject to CH4_stor_c1{u in UnitsOfType['CH4storage'], hy in Year}:
	CH4_stor_stored[u,hy] <= CH4_stor_limit_ch[u]*Units_Mult[u];

subject to CH4_stor_c2{u in UnitsOfType['CH4storage'], hy in Year}:
	CH4_stor_stored[u,hy] >= CH4_stor_limit_di[u]*Units_Mult[u];

#-- Power constraints
subject to CH4_stor_c3{u in UnitsOfType['CH4storage'], p in PeriodStandard,t in Time[p]}:
	Units_demand['Biomethane',u,p,t]*dt[p] <= (CH4_stor_limit_ch[u]-CH4_stor_limit_di[u])*Units_Mult[u]*C_rate_CH4[u];

subject to CH4_stor_c4{u in UnitsOfType['CH4storage'], p in PeriodStandard,t in Time[p]}:
	Units_supply['Biomethane',u,p,t]*dt[p] <= (CH4_stor_limit_ch[u]-CH4_stor_limit_di[u])*Units_Mult[u]*C_rate_CH4[u];

# never charge and discharge storage simultaneously:
subject to is_stor_CH4_discharging{u in UnitsOfType['CH4storage'], p in Period, t in Time[p]}:
    Units_supply['Biomethane',u,p,t] <= mode_discharge_CH4[u,p,t] * M_stor_CH4;

subject to is_stor_CH4_charging{u in UnitsOfType['CH4storage'], p in Period, t in Time[p]}:
    Units_demand['Biomethane',u,p,t] <= mode_charge_CH4[u,p,t] * M_stor_CH4;

subject to no_charg_discharg_CH4{u in UnitsOfType['CH4storage'], p in Period, t in Time[p]}:
    mode_discharge_CH4[u,p,t] + mode_charge_CH4[u,p,t] <= 1;