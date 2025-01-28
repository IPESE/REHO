#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# CH4 storage tank
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param CH4_stor_eff_charge{u in UnitsOfType['CH4storage']} 	default 1;	#- AC-AC efficiency
param CH4_stor_eff_discharge{u in UnitsOfType['CH4storage']} 	default 1;	#- AC-AC efficiency

param CH4_stor_limit_ch{u in UnitsOfType['CH4storage']} default 1;			#-	[2]
param CH4_stor_limit_di{u in UnitsOfType['CH4storage']} default 0;			#-	[1]

param C_rate_CH4{u in UnitsOfType['CH4storage']} default 1;					#-
param CH4_stor_self_discharge{u in UnitsOfType['CH4storage']} default 1;	#-	[1]

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

#------------------------------------------------------------------------------------------
# COMPRESSION (link electricity consumption to the storage itself (easier for result interpretation) but use it for
# sizing the compressor (taking thus the CAPEX into account). The unit Compressor_IP is defined in the .csv but does not
# require any demand/supply relative to REHO. The same compressor can be used for all gases, and the CAPEX will be scaled
# with the maximum storage electrical need.
#------------------------------------------------------------------------------------------

param compr_isentropic_eff_CH4{u in UnitsOfType['CH4storage']}  default 0.72;  # Isentropic efficiency (-)
param R_const_CH4{u in UnitsOfType['CH4storage']}  				:= 8.314;      # Universal gas constant (J/(mol*K))
param T_compr_in_CH4{u in UnitsOfType['CH4storage']}  			:= 293.15;     # Inlet temperature (K)
param M_CH4{u in UnitsOfType['CH4storage']} 				:= 16*1e-3;	   # Molar mass of Ch4 (kg/mol)
param k_CH4{u in UnitsOfType['CH4storage']}  				:= 1.31;       # Heat capacity ratio for CH4
param LHV_CH4{u in UnitsOfType['CH4storage']}  				:= 50000;     # LHV of CH4 (kJ/kg)

# Compressibility factor (linear regression) valid for pressure [1 to 100 bars]
param Z_intercept_CH4 := 1.0034;
param Z_slope_CH4 	  := -0.0007;

param pressure_in_CH4 		default 15;	 # pressure at outlet of SOEC
param CH4_stor_pressure		default 75; # storage pressure of CH4

# Chosse the compress. factor Z at the midpoint pressure for simplicity
param Z_CH4 := Z_intercept_CH4 + Z_slope_CH4*(pressure_in_CH4+CH4_stor_pressure)/2;

# Calculate electrical power required for CH4 pressurization
subject to elec_CH4_calc{u in UnitsOfType['CH4storage'], p in Period,t in Time[p]}:
	Units_demand['Electricity',u,p,t] = Units_demand['Biomethane',u,p,t] / (LHV_CH4[u]) * (R_const_CH4[u]/M_CH4[u]) * Z_CH4 * k_CH4[u] * T_compr_in_CH4[u]
										/ (compr_isentropic_eff_CH4[u]*(k_CH4[u]-1)) * ((CH4_stor_pressure/pressure_in_CH4)^((k_CH4[u]-1)/k_CH4[u]) - 1)/1e3;

# This equation causes convergence issue apparently (since also present for the same storage for CO2).
#--Size of compressor based on electrical input power
#subject to mult_compressor_CH4{u in UnitsOfType['CH4storage'], c in UnitsOfType['Compressor'], p in Period,t in Time[p]}:
#	Units_demand['Electricity',u,p,t]+1 <= Units_Mult[c];
