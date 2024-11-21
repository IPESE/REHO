#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Battery (adapted to inter-period storage)
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#-First-order electrical storage model including:
#	1. dis-/charging efficiencies
#	2. self-discharging efficiency
#	3. dis-/charging limits
#-References :
# [1]	F. Oldewurtel et al., Building Control and Storage Management with [...], 2010
# [2]   M. Koller et al., Defining a Degradation Cost Function for Optimal [...], 2013

#-Adapted model to additionally include :
# [3] Efficiency degradation over time (efficiency used is an average of the battery efficiency over its lifetime)
# [4] C-rate limitation (beware that maximum C-rate value is 1 (due to hourly resolution))

param BAT_eff_charge_IP{u in UnitsOfType['Battery_interperiod']} 	default 0.95;	#- AC-AC efficiency
param BAT_eff_discharge_IP{u in UnitsOfType['Battery_interperiod']} 	default 0.95;	#- AC-AC efficiency

param BAT_limit_ch_IP{u in UnitsOfType['Battery_interperiod']} default 0.6;			#-	[2]
param BAT_limit_di_IP{u in UnitsOfType['Battery_interperiod']} default 0.2;			#-	[1]

param C_rate_IP{u in UnitsOfType['Battery_interperiod']} default 1;					#-
param BAT_self_discharge_IP{u in UnitsOfType['Battery_interperiod']} default 0.99992;	#-	[1]

# param BAT_RTE_degradation_IP{u in UnitsOfType['Battery_interperiod']} default 0.005; # Battery efficiency degradation per year
# param BAT_efficiency_IP{u in UnitsOfType['Battery_interperiod']} >=0, <= sqrt(BAT_eff_RTE_basis_IP[u]) := sqrt(BAT_eff_RTE_basis_IP[u]-BAT_RTE_degradation_IP[u]*lifetime[u]/2); #Computation of the one way efficiency (assuming equal efficiency out and in)

var BAT_E_charging{u in UnitsOfType['Battery_interperiod'], p in Period,t in Time[p]} >= 0;
var BAT_E_discharging{u in UnitsOfType['Battery_interperiod'], p in Period,t in Time[p]} >= 0;
var BAT_E_stored_IP{u in UnitsOfType['Battery_interperiod'], hy in Year} >= 0;

subject to BAT_charging_process_IP{u in UnitsOfType['Battery_interperiod'], p in Period,t in Time[p]}:
	BAT_E_charging[u,p,t] = BAT_eff_charge_IP[u]*Units_demand['Electricity',u,p,t];

subject to BAT_discharging_process_IP{u in UnitsOfType['Battery_interperiod'], p in Period,t in Time[p]}:
	BAT_E_discharging[u,p,t] = 1/BAT_eff_discharge_IP[u]*Units_supply['Electricity',u,p,t];

#--Hourly Energy balance (valid for inter-period storage)
subject to BAT_energy_balance_IP{u in UnitsOfType['Battery_interperiod'], hy in Year diff {last(Year)}}:
	BAT_E_stored_IP[u,next(hy,Year)] = BAT_self_discharge_IP[u]*BAT_E_stored_IP[u,hy] +
	(BAT_E_charging[u,PeriodOfYear[hy],TimeOfYear[hy]] - BAT_E_discharging[u,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];

#--SoC constraints
subject to BAT_c1_IP{u in UnitsOfType['Battery_interperiod'], hy in Year}:
	BAT_E_stored_IP[u,hy] <= BAT_limit_ch_IP[u]*Units_Mult[u];

subject to BAT_c2_IP{u in UnitsOfType['Battery_interperiod'], hy in Year}:
	BAT_E_stored_IP[u,hy] >= BAT_limit_di_IP[u]*Units_Mult[u];

#-- Power constraints
subject to BAT_c3_IP{u in UnitsOfType['Battery_interperiod'],p in PeriodStandard,t in Time[p]}:
	Units_demand['Electricity',u,p,t]*dt[p] <= (BAT_limit_ch_IP[u]-BAT_limit_di_IP[u])*Units_Mult[u]*C_rate_IP[u];

subject to BAT_c4_IP{u in UnitsOfType['Battery_interperiod'],p in PeriodStandard,t in Time[p]}:
	Units_supply['Electricity',u,p,t]*dt[p] <= (BAT_limit_ch_IP[u]-BAT_limit_di_IP[u])*Units_Mult[u]*C_rate_IP[u];

#--Cyclic
subject to BAT_E_stored_IP_cyclic{u in UnitsOfType['Battery_interperiod']}:
BAT_E_stored_IP[u,first(Year)] = BAT_self_discharge_IP[u]*BAT_E_stored_IP[u,last(Year)] +
	(BAT_E_charging[u,PeriodOfYear[last(Year)],TimeOfYear[last(Year)]] - BAT_E_discharging[u,PeriodOfYear[last(Year)],TimeOfYear[last(Year)]])*dt[PeriodOfYear[last(Year)]];
