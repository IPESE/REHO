#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# H2 storage tank
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param H2_stor_eff_charge{u in UnitsOfType['H2storage']} 	default 1;	#- AC-AC efficiency
param H2_stor_eff_discharge{u in UnitsOfType['H2storage']} 	default 1;	#- AC-AC efficiency

param H2_stor_limit_ch{u in UnitsOfType['H2storage']} default 1;			#-	[2]
param H2_stor_limit_di{u in UnitsOfType['H2storage']} default 0;			#-	[1]

param C_rate_H2{u in UnitsOfType['H2storage']} default 1;					#-
param H2_stor_self_discharge{u in UnitsOfType['H2storage']} default 1;	#-	[1]
param H2_stor_elec_eff{u in UnitsOfType['H2storage']} default 0.1134; #at high pressure 500 bars

# param H2_stor_RTE_degradation{u in UnitsOfType['H2storage']} default 0.005; # H2_stortery efficiency degradation per year
# param H2_stor_efficiency{u in UnitsOfType['H2storage']} >=0, <= sqrt(H2_stor_eff_RTE_basis[u]) := sqrt(H2_stor_eff_RTE_basis[u]-H2_stor_RTE_degradation[u]*lifetime[u]/2); #Computation of the one way efficiency (assuming equal efficiency out and in)

var H2_stor_charging{u in UnitsOfType['H2storage'], p in Period,t in Time[p]} >= 0;
var H2_stor_discharging{u in UnitsOfType['H2storage'], p in Period,t in Time[p]} >= 0;
var H2_stor_stored{u in UnitsOfType['H2storage'], hy in Year} >= 0;

var mode_charge_H2{u in UnitsOfType['H2storage'], p in Period, t in Time[p]} binary := 0;
var mode_discharge_H2{u in UnitsOfType['H2storage'], p in Period, t in Time[p]} binary := 0;
param M_stor_H2 := 1e6;

subject to H2_stor_charging_process{u in UnitsOfType['H2storage'], p in Period,t in Time[p]}:
	H2_stor_charging[u,p,t] = H2_stor_eff_charge[u]*Units_demand['Hydrogen',u,p,t];

subject to H2_stor_discharging_process{u in UnitsOfType['H2storage'], p in Period,t in Time[p]}:
	H2_stor_discharging[u,p,t] = 1/H2_stor_eff_discharge[u]*Units_supply['Hydrogen',u,p,t];

subject to H2_stor_elec_use{u in UnitsOfType['H2storage'], p in Period,t in Time[p]}:
	Units_demand['Electricity',u,p,t] = Units_demand['Hydrogen',u,p,t] * H2_stor_elec_eff[u];

#--Hourly Energy balance (valid for inter-period storage)
subject to H2_stor_energy_balance{u in UnitsOfType['H2storage'], hy in Year}:
	H2_stor_stored[u,next(hy,Year)] = H2_stor_self_discharge[u]*H2_stor_stored[u,hy] +
	(H2_stor_charging[u,PeriodOfYear[hy],TimeOfYear[hy]] - H2_stor_discharging[u,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];

#--SoC constraints
subject to H2_stor_c1{u in UnitsOfType['H2storage'], hy in Year}:
	H2_stor_stored[u,hy] <= H2_stor_limit_ch[u]*Units_Mult[u];

subject to H2_stor_c2{u in UnitsOfType['H2storage'], hy in Year}:
	H2_stor_stored[u,hy] >= H2_stor_limit_di[u]*Units_Mult[u];

#-- Power constraints
subject to H2_stor_c3{u in UnitsOfType['H2storage'],p in PeriodStandard,t in Time[p]}:
	Units_demand['Hydrogen',u,p,t]*dt[p] <= (H2_stor_limit_ch[u]-H2_stor_limit_di[u])*Units_Mult[u]*C_rate_H2[u];

subject to H2_stor_c4{u in UnitsOfType['H2storage'],p in PeriodStandard,t in Time[p]}:
	Units_supply['Hydrogen',u,p,t]*dt[p] <= (H2_stor_limit_ch[u]-H2_stor_limit_di[u])*Units_Mult[u]*C_rate_H2[u];

# never charge and discharge storage simultaneously:
subject to is_stor_H2_discharging{u in UnitsOfType['H2storage'], p in Period, t in Time[p]}:
    Units_supply['Hydrogen',u,p,t] <= mode_discharge_H2[u,p,t] * M_stor_H2;

subject to is_stor_H2_charging{u in UnitsOfType['H2storage'], p in Period, t in Time[p]}:
    Units_demand['Hydrogen',u,p,t] <= mode_charge_H2[u,p,t] * M_stor_H2;

subject to no_charg_discharg_H2{u in UnitsOfType['H2storage'], p in Period, t in Time[p]}:
    mode_discharge_H2[u,p,t] + mode_charge_H2[u,p,t] <= 1;