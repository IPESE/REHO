#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# H2 storage tank, interperiod (8760 hours) including electricity needs for compression. This is calculated below
# separately depending on the storage pressure and the properties of the gas.
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param H2_stor_eff_charge{u in UnitsOfType['H2storage']} 	default 1;	#- AC-AC efficiency
param H2_stor_eff_discharge{u in UnitsOfType['H2storage']} 	default 1;	#- AC-AC efficiency

param H2_stor_limit_ch{u in UnitsOfType['H2storage']} default 1;			#-	[2]
param H2_stor_limit_di{u in UnitsOfType['H2storage']} default 0;			#-	[1]

param C_rate_H2{u in UnitsOfType['H2storage']} default 1;					#-
param H2_stor_self_discharge{u in UnitsOfType['H2storage']} default 1;	#-	[1]

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

#------------------------------------------------------------------------------------------
# COMPRESSION (link electricity consumption to the storage itself (easier for result interpretation) but use it for
# sizing the compressor (taking thus the CAPEX into account). The unit Compressor_IP is defined in the .csv but does not
# require any demand/supply relative to REHO. The same compressor can be used for all gases, and the CAPEX will be scaled
# with the maximum storage electrical need.
#------------------------------------------------------------------------------------------

param compr_isentropic_eff_H2{u in UnitsOfType['H2storage']}       default 0.72; 					  # Isentropic efficiency (-)
param R_const_H2{u in UnitsOfType['H2storage']}  					:= 8.314;          				  # Universal gas constant (J/(mol*K))
param T_compr_in_H2{u in UnitsOfType['H2storage']} 				    := 293.15;        				  # Inlet temperature (K)
param M_H2{u in UnitsOfType['H2storage']} 						:= 2*1e-3;						  # Molar mass of H2 (kg/mol)
param k_H2{u in UnitsOfType['H2storage']} 						:= 1.41;       					  # Heat capacity ratio for H2
param LHV_H2{u in UnitsOfType['H2storage']} 					:= 120000;   					  # LHV of H2 (kJ/kg)

# Compressibility factor (linear regression) valid for pressure [1 to 500 bars]
param Z_intercept_H2 := 1.0237;
param Z_slope_H2 	  := 0.0008;

param pressure_in_H2 					 		default 1;	 # pressure at outlet of SOEC
param H2_stor_pressure							default 350; # storage pressure of H2

# Chosse the compress. factor Z at the midpoint pressure for simplicity
param Z_H2 := Z_intercept_H2 + Z_slope_H2*(pressure_in_H2+H2_stor_pressure)/2;

# Calculate electrical power required for H2 pressurization
subject to elec_H2_calc{u in UnitsOfType['H2storage'], p in Period,t in Time[p]}:
	Units_demand['Electricity',u,p,t] = Units_demand['Hydrogen',u,p,t] / (LHV_H2[u]) * (R_const_H2[u]/M_H2[u]) * T_compr_in_H2[u] * k_H2[u] * Z_H2
										/ (compr_isentropic_eff_H2[u]*(k_H2[u]-1)) * ((H2_stor_pressure/pressure_in_H2)^((k_H2[u]-1)/k_H2[u]) - 1)/1e3;

#--Size of compressor based on electrical input power
subject to mult_compressor_H2{u in UnitsOfType['H2storage'], c in UnitsOfType['Compressor'], p in Period,t in Time[p]}:
	Units_demand['Electricity',u,p,t] <= Units_Mult[c];



