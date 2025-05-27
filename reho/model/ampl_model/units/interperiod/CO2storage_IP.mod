#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# CO2 storage tank
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param CO2_stor_eff_charge{u in UnitsOfType['CO2storage']} 	default 1;	#- AC-AC efficiency
param CO2_stor_eff_discharge{u in UnitsOfType['CO2storage']} 	default 1;	#- AC-AC efficiency

param CO2_stor_limit_max{u in UnitsOfType['CO2storage']} default 1;			#-	[2]
param CO2_stor_limit_min{u in UnitsOfType['CO2storage']} default 0;			#-	[1]

param C_rate_CO2{u in UnitsOfType['CO2storage']} default 1;					#-
param CO2_stor_self_discharge{u in UnitsOfType['CO2storage']} default 1;	#-	[1]

var CO2_stor_charging{u in UnitsOfType['CO2storage'], p in Period,t in Time[p]} >= 0;
var CO2_stor_discharging{u in UnitsOfType['CO2storage'], p in Period,t in Time[p]} >= 0;
var CO2_stor_stored{u in UnitsOfType['CO2storage'], hy in Year} >= 0;
var CO2_stor_volume{u in UnitsOfType['CO2storage']} >= 0;

var mode_charge_CO2{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]} binary := 0;
var mode_discharge_CO2{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]} binary := 0;
param M_stor_CO2 := 1e7;

subject to CO2_stor_charging_process{u in UnitsOfType['CO2storage'], p in Period,t in Time[p]}:
	CO2_stor_charging[u,p,t] = CO2_stor_eff_charge[u]*Units_demand['CO2',u,p,t];

subject to CO2_stor_discharging_process{u in UnitsOfType['CO2storage'], p in Period,t in Time[p]}:
	CO2_stor_discharging[u,p,t] = 1/CO2_stor_eff_discharge[u]*Units_supply['CO2',u,p,t];

#--Hourly Energy balance (valid for inter-period storage)
subject to CO2_stor_energy_balance{u in UnitsOfType['CO2storage'], hy in Year}:
	CO2_stor_stored[u,next(hy,Year)] = CO2_stor_self_discharge[u]*CO2_stor_stored[u,hy] +
	(CO2_stor_charging[u,PeriodOfYear[hy],TimeOfYear[hy]] - CO2_stor_discharging[u,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];

# never charge and discharge storage simultaneously:
subject to is_stor_CO2_discharging{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]}:
    Units_supply['CO2',u,p,t] <= mode_discharge_CO2[u,p,t] * M_stor_CO2;

subject to is_stor_CO2_charging{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]}:
    Units_demand['CO2',u,p,t] <= mode_charge_CO2[u,p,t] * M_stor_CO2;

subject to no_charg_discharg_CO2{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]}:
    mode_discharge_CO2[u,p,t] + mode_charge_CO2[u,p,t] <= 1;

#------------------------------------------------------------------------------------------
# COMPRESSION (link electricity consumption to the storage itself (easier for result interpretation) but use it for
# sizing the compressor (taking thus the CAPEX into account). The unit Compressor_IP is defined in the .csv but does not
# require any demand/supply relative to REHO. The same compressor can be used for all gases, and the CAPEX will be scaled
# with the maximum storage electrical need.
#------------------------------------------------------------------------------------------

param compr_isentropic_eff_CO2  							:= 0.72;  # Isentropic efficiency (-)
param R_const_CO2  											:= 8.314;      # Universal gas constant (J/(mol*K))
param T_compr_in_CO2  										:= 293.15;     # Inlet temperature (K)
param M_CO2 												:= 44*1e-3;	   # Molar mass of CO2 (kg/mol)
param k_CO2  												:= 1.30;       # Heat capacity ratio for CO2
param LHV_CO2  												:= 0;     	   # LHV of CO2 (kJ/kg)

# Compressibility factor (linear regression) valid for pressure [1 to 100 bars]
param Z_intercept_CO2 										:= 0.9934;
param Z_slope_CO2 	  										:= -0.0054;

param pressure_in_CO2 		      							default 1;	 # pressure at outlet of SOEC
param CO2_stor_pressure 		  							default 75;  # storage pressure of CO2

# Chosse the compress. factor Z at the midpoint pressure for simplicity
param Z_CO2 												:= Z_intercept_CO2 + Z_slope_CO2*(pressure_in_CO2+CO2_stor_pressure)/2;
param Z_CO2_max 											:= Z_intercept_CO2 + Z_slope_CO2*CO2_stor_pressure;

# Calculate electrical power required for CO2 pressurization
subject to elec_CO2_calc{u in UnitsOfType['CO2storage'], p in Period, t in Time[p]}:
	Units_demand['Electricity',u,p,t] = Units_demand['CO2',u,p,t]/3600 * M_CO2 * (R_const_CO2/M_CO2) * T_compr_in_CO2 * k_CO2 * Z_CO2
										/ (compr_isentropic_eff_CO2*(k_CO2-1)) * ((CO2_stor_pressure/pressure_in_CO2)^((k_CO2-1)/k_CO2) - 1)/1e3;

#--Size of compressor based on electrical input power
subject to mult_compressor_CO2{u in UnitsOfType['CO2storage'], c in UnitsOfType['Compressor'], p in Period, t in Time[p]}:
	Units_demand['Electricity',u,p,t] <= Units_Mult[c];

#--SoC constraints
subject to CO2_stor_c1{u in UnitsOfType['CO2storage'], hy in Year}:
	Units_Mult[u] * CO2_stor_limit_max[u] >= CO2_stor_stored[u,hy];

subject to CO2_stor_c2{u in UnitsOfType['CO2storage'], hy in Year}:
	Units_Mult[u] * CO2_stor_limit_min[u] <= CO2_stor_stored[u,hy];

#--SoC constraints
subject to CO2_stor_c3{u in UnitsOfType['CO2storage'], hy in Year}:
	CO2_stor_volume[u] >= Units_Mult[u] * Z_CO2_max * R_const_CO2 * T_compr_in_CO2 / (CO2_stor_pressure * 10^5);

subject to CO2_stor_c4{u in UnitsOfType['CO2storage'], hy in Year}:
	CO2_stor_volume[u] <= Units_Mult[u] * Z_CO2_max * R_const_CO2 * T_compr_in_CO2 / (CO2_stor_pressure * 10^5);

#-- Power constraints
#subject to CO2_stor_c3{u in UnitsOfType['CO2storage'], p in PeriodStandard, t in Time[p]}:
#	Units_demand['CO2',u,p,t]*dt[p] <= (CO2_stor_limit_max[u]-CO2_stor_limit_min[u])*Units_Mult[u]*C_rate_CO2[u];

#subject to CO2_stor_c4{u in UnitsOfType['CO2storage'],p in PeriodStandard,t in Time[p]}:
#	Units_supply['CO2',u,p,t]*dt[p] <= (CO2_stor_limit_max[u]-CO2_stor_limit_min[u])*Units_Mult[u]*C_rate_CO2[u];
