#-First-order electrical storage model including:
#	1. dis-/charging efficiencies
#	2. self-discharging efficiency
#	3. dis-/charging limits
#-References :
# [1]	F. Oldewurtel et al., Building Control and Storage Management with [...], 2010
# [2]   M. Koller et al., Defining a Degradation Cost Function for Optimal [...], 2013

#-Adapted model to additionally include :
# [3] Efficiency degradation over time (efficiency used is an average of the H2_stortery efficiency over its lifetime)
# [4] C-rate limitation (beware that maximum C-rate value is 1 (due to hourly resolution))

param H2_stor_eff_charge{u in UnitsOfType['H2storage']} 	default 1;	#- AC-AC efficiency
param H2_stor_eff_discharge{u in UnitsOfType['H2storage']} 	default 1;	#- AC-AC efficiency

param H2_stor_limit_ch{u in UnitsOfType['H2storage']} default 1;			#-	[2]
param H2_stor_limit_di{u in UnitsOfType['H2storage']} default 0;			#-	[1]

param C_rate_H2{u in UnitsOfType['H2storage']} default 1;					#-
param H2_stor_self_discharge{u in UnitsOfType['H2storage']} default 1;	#-	[1]
param H2_stor_efficiency{u in UnitsOfType['H2storage']} default 0.1134; #at high pressure 500 bars

# param H2_stor_RTE_degradation{u in UnitsOfType['H2storage']} default 0.005; # H2_stortery efficiency degradation per year
# param H2_stor_efficiency{u in UnitsOfType['H2storage']} >=0, <= sqrt(H2_stor_eff_RTE_basis[u]) := sqrt(H2_stor_eff_RTE_basis[u]-H2_stor_RTE_degradation[u]*lifetime[u]/2); #Computation of the one way efficiency (assuming equal efficiency out and in)

var H2_stor_charging{h in House, u in UnitsOfType['H2storage'] inter UnitsOfHouse[h], p in Period,t in Time[p]} >= 0;
var H2_stor_discharging{h in House, u in UnitsOfType['H2storage'] inter UnitsOfHouse[h], p in Period,t in Time[p]} >= 0;
var H2_stor_stored{h in House, u in UnitsOfType['H2storage'] inter UnitsOfHouse[h], hy in Year} >= 0;

var mode_charge_H2{u in UnitsOfType['H2storage'], p in Period, t in Time[p]} binary;
var mode_discharge_H2{u in UnitsOfType['H2storage'], p in Period, t in Time[p]} binary;
param M_stor_H2 := 1e12;

subject to H2_stor_charging_process{h in House,u in UnitsOfType['H2storage'] inter UnitsOfHouse[h], p in Period,t in Time[p]}:
	H2_stor_charging[h,u,p,t] = H2_stor_eff_charge[u]*Units_demand['Hydrogen',u,p,t];

subject to H2_stor_elec_use{h in House,u in UnitsOfType['H2storage'] inter UnitsOfHouse[h], p in Period,t in Time[p]}:
	Units_demand['Electricity',u,p,t] = H2_stor_charging[h,u,p,t] * H2_stor_efficiency[u];

subject to H2_stor_discharging_process{h in House,u in UnitsOfType['H2storage'] inter UnitsOfHouse[h], p in Period,t in Time[p]}:
	H2_stor_discharging[h,u,p,t] = 1/H2_stor_eff_discharge[u]*Units_supply['Hydrogen',u,p,t];

#--Hourly Energy balance (valid for inter-period storage)
subject to H2_stor_energy_balance{h in House,u in UnitsOfType['H2storage'] inter UnitsOfHouse[h], hy in Year}:
	H2_stor_stored[h,u,next(hy,Year)] = H2_stor_self_discharge[u]*H2_stor_stored[h,u,hy] +
	(H2_stor_charging[h,u,PeriodOfYear[hy],TimeOfYear[hy]] - H2_stor_discharging[h,u,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];

#--SoC constraints
subject to H2_stor_c1{h in House,u in UnitsOfType['H2storage'] inter UnitsOfHouse[h], hy in Year}:
	H2_stor_stored[h,u,hy] <= H2_stor_limit_ch[u]*Units_Mult[u];

subject to H2_stor_c2{h in House,u in UnitsOfType['H2storage'] inter UnitsOfHouse[h], hy in Year}:
	H2_stor_stored[h,u,hy] >= H2_stor_limit_di[u]*Units_Mult[u];

#-- Power constraints
subject to H2_stor_c3{h in House,u in UnitsOfType['H2storage'] inter UnitsOfHouse[h],p in PeriodStandard,t in Time[p]}:
	Units_demand['Hydrogen',u,p,t]*dt[p] <= (H2_stor_limit_ch[u]-H2_stor_limit_di[u])*Units_Mult[u]*C_rate_H2[u];

subject to H2_stor_c4{h in House,u in UnitsOfType['H2storage'] inter UnitsOfHouse[h],p in PeriodStandard,t in Time[p]}:
	Units_supply['Hydrogen',u,p,t]*dt[p] <= (H2_stor_limit_ch[u]-H2_stor_limit_di[u])*Units_Mult[u]*C_rate_H2[u];

# never charge and discharge storage simultaneously:
subject to is_stor_H2_discharging{u in UnitsOfType['H2storage'], p in Period, t in Time[p]}:
    Units_supply['Hydrogen',u,p,t] <= mode_discharge_H2[u,p,t] * M_stor_H2;

subject to is_stor_H2_charging{u in UnitsOfType['H2storage'], p in Period, t in Time[p]}:
    Units_demand['Hydrogen',u,p,t] <= mode_charge_H2[u,p,t] * M_stor_H2;

subject to no_charg_discharg_H2{u in UnitsOfType['H2storage'], p in Period, t in Time[p]}:
    mode_discharge_H2[u,p,t] + mode_charge_H2[u,p,t] <= 1;