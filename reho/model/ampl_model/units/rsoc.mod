#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Reversible Solid Oxide Cells (rSOC) is a technology that can operate in both modes, either producing electricity from
# various fuels (H2, CH4, ...) or converting excess electricity into molecules, allowing for long-term seasonal storage.
# The rSOCs are known for their high electrical/conversion efficiencies, thanks to the high operating temperatures (>700 °C)
# and also outputs high quality heat that can be recovered for further electricity production, industrial processes or
# even district heating networks. This is valid in both modes (Fuel cell or Electrolyzer), at different temperatures and
# quantities. The electrolyzer mode can operate at higher current densities, resulting (with the higher voltage due to
# thermodynamic considerations) in a power input 3 times higher than the output SOFC power. Typical module sizes would
# be 50 kW fuel cell (=150 kW Electrolyzer).
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# These efficiencies come from Aspen/OSMOSE modelling (Arthur Waeber / Xinyi Wei / Shivom Sharma)
param SOFC_elec_eff_H2{u in UnitsOfType['rSOC']} >=0, <=1 default 0.6209; # (elec output/H2 LHV) Optimal design, rounded down
param SOFC_therm_eff_H2_high_T{u in UnitsOfType['rSOC']} >=0, <=1 default 0.4174; # (heat output/H2 LHV) including condensation of produced steam
param SOFC_therm_eff_H2_mid_T{u in UnitsOfType['rSOC']} >=0, <=1 default 0.0194; # (heat output/H2 LHV) including condensation of produced steam
param SOFC_therm_eff_H2_low_T{u in UnitsOfType['rSOC']} >=0, <=1 default 0.1162; # (heat output/H2 LHV) including condensation of produced steam

param SOFC_elec_eff_CH4{u in UnitsOfType['rSOC']} >=0, <=1 default 0.6430; # (elec output/CH4 LHV) Optimal design rounded down
param SOFC_therm_eff_CH4_high_T{u in UnitsOfType['rSOC']} >=0, <=1 default 0.2972; # (heat output/CH4 LHV) including condensation of produced steam
param SOFC_therm_eff_CH4_mid_T{u in UnitsOfType['rSOC']} >=0, <=1 default 0.0413; # (heat output/CH4 LHV) including condensation of produced steam
param SOFC_therm_eff_CH4_low_T{u in UnitsOfType['rSOC']} >=0, <=1 default 0.1043; # (heat output/CH4 LHV) including condensation of produced steam

param SOEC_conv_eff{u in UnitsOfType['rSOC']} >=0, <=1 default 0.9543; # (H2 LHV/elec input) eff (includes High T heat that is provided through electrical heaters)
param SOEC_therm_eff_high_T{u in UnitsOfType['rSOC']} <=1 default -0.1794; # (heat input/elec input) eff # Requires Heat (since Methanator is modelled appart) rounded up since heat required
param SOEC_therm_eff_mid_T{u in UnitsOfType['rSOC']} <=1 default 0.0000; # (heat input/elec input) eff # Requires Heat (since Methanator is modelled appart) rounded up since heat required
param SOEC_therm_eff_low_T{u in UnitsOfType['rSOC']} <=1 default 0.021; # (heat input/elec input) eff # Requires Heat (since Methanator is modelled appart) rounded up since heat required

param SOEC_power_max_limit_in{u in UnitsOfType['rSOC']} >=0 default 3;
param SOFC_power_max_limit_out{u in UnitsOfType['rSOC']} >=0 default 1;
param SOEC_power_min_limit_in{u in UnitsOfType['rSOC']} >=0 default 0;
param SOFC_power_min_limit_out{u in UnitsOfType['rSOC']} >=0 default 0;

param bigM_rSOC >= 0 default 1e6;

param mol_h_CO2_per_kW_CH4{u in UnitsOfType['rSOC']} >=0 default 1/(0.016*49.7/3.6); # Conversion from kWh CH4 to mol Ch4 --> mol CO2

var mode_SOFC{u in UnitsOfType['rSOC'], p in Period, t in Time[p]} binary := 0;
var mode_SOEC{u in UnitsOfType['rSOC'], p in Period, t in Time[p]} binary := 0;

subject to SOFC_energy_balance{u in UnitsOfType['rSOC'], p in Period,t in Time[p]}:
    Units_supply['Electricity',u,p,t] =
    SOFC_elec_eff_H2[u]*Units_demand['Hydrogen',u,p,t] +
    SOFC_elec_eff_CH4[u]*Units_demand['Biomethane',u,p,t];

subject to SOEC_energy_balance{u in UnitsOfType['rSOC'], p in Period,t in Time[p]}:
    Units_supply['Hydrogen',u,p,t] = SOEC_conv_eff[u]*Units_demand['Electricity',u,p,t];

subject to SOFC_energy_balance_2{u in UnitsOfType['rSOC'], p in Period,t in Time[p]}:
    Units_supply['CO2',u,p,t] <= mol_h_CO2_per_kW_CH4[u]*Units_demand['Biomethane',u,p,t]; # Not forced to store all the produce CO2 (easier for storage convergence)

#-hot streams heat leaving SOFC (80-60°C)
subject to SOFC_Usable_heat_computation{h in House,u in UnitsOfType['rSOC'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
    Units_demand['Hydrogen',u,p,t]*(SOFC_therm_eff_H2_high_T[u] + SOFC_therm_eff_H2_mid_T[u])
    + Units_demand['Biomethane',u,p,t]*(SOFC_therm_eff_CH4_high_T[u] + SOFC_therm_eff_CH4_mid_T[u])
    >= sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];

#######################################################################################################################
####################### HOW TO ADD A COLD STREAM INTEGRATED TO THE HEAT CASCADE TO A UNIT ? ###########################
#######################################################################################################################
# Add the 'NewService' (here 'rSOC') to the <infrastructure.py> (line 49: self.Services = np.array(['DHW', 'SH', 'Cooling', 'rSOC'])) #
# Add in <building_units.csv> that there is a cold stream within this unit:
#        - UnitOfService: 'rSOC'
#        - StreamsOfUnit: 'c_ht' (can be any of the pre-defined cold_streams)
#        - Stream_Tin // Stream_Tout: 80/ 60 // 60/ 80; (the first one is for the hot stream, the second for the cold stream)
#        - Type down the constraint as follows: YourHeatFlow = Streams_Q['rSOC','rSOC_Building1_c_ht',p,t]
#######################################################################################################################

subject to SOEC_required_heat_computation{h in House, u in UnitsOfType['rSOC'] inter UnitsOfHouse[h], st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hout[st] = 1}:
  -Units_demand['Electricity',u,p,t]*SOEC_therm_eff_high_T[u] = Streams_Q['rSOC_heat',st,p,t];

# Force mode_SOFC to be 1 when power is supplied
subject to SOFC_mode_on{u in UnitsOfType['rSOC'], p in Period, t in Time[p]}:
    Units_supply['Electricity',u,p,t] <= bigM_rSOC * mode_SOFC[u,p,t];

# Force mode_SOEC to be 1 when power is supplied
subject to SOEC_mode_on{u in UnitsOfType['rSOC'], p in Period, t in Time[p]}:
    Units_demand['Electricity',u,p,t] <= bigM_rSOC * mode_SOEC[u,p,t];

# Never both modes simultaneously
subject to no_2_modes_simultaneously{u in UnitsOfType['rSOC'],p in Period, t in Time[p]}:
    mode_SOFC[u,p,t] + mode_SOEC[u,p,t] <= 1;

# Power limitation
subject to SOFC_mult{u in UnitsOfType['rSOC'],p in Period, t in Time[p]}:
    Units_supply['Electricity',u,p,t] <= Units_Mult[u]*SOFC_power_max_limit_out[u];

subject to SOEC_mult{u in UnitsOfType['rSOC'],p in Period, t in Time[p]}:
    Units_demand['Electricity',u,p,t] <= Units_Mult[u]*SOEC_power_max_limit_in[u];

subject to low_T_heat_available_rSOC{u in UnitsOfType['rSOC'], p in Period, t in Time[p]}:
    waste_heat_available[p,t] <= SOFC_therm_eff_H2_low_T[u]*Units_demand['Hydrogen',u,p,t] + SOFC_therm_eff_CH4_low_T[u]*Units_demand['Biomethane',u,p,t] + SOEC_therm_eff_low_T[u]*Units_demand['Electricity',u,p,t];

/*
# Part load limitations usibg bigM method to allow the electricity flow to be either 0 or at least the minimal threshold
# SOFC mode part-load constraint
subject to SOFC_partload{u in UnitsOfType['rSOC'], p in Period, t in Time[p]}:
    Units_supply['Electricity',u,p,t] = 0
    or Units_supply['Electricity',u,p,t] >= Units_Mult[u] * SOFC_power_min_limit_out[u];

# SOEC mode part-load constraint
subject to SOEC_partload{u in UnitsOfType['rSOC'],p in Period, t in Time[p]}:
    Units_demand['Electricity',u,p,t] = 0
    or Units_demand['Electricity',u,p,t] >= Units_Mult[u] * SOEC_power_min_limit_in[u];
*/