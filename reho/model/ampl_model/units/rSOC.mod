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

# These efficiencies come from Aspen/OSMOSE modelling (Arthur Waeber/ Xinyi Wei / Shivom Sharma)
param SOFC_elec_eff{u in UnitsOfType['rSOC']} >=0, <=1 default 0.62; # (elec output/H2 LHV) eff
param SOFC_therm_eff{u in UnitsOfType['rSOC']} >=0, <=1 default 0.2; # (elec output/H2 LHV) eff
param SOEC_conv_eff{u in UnitsOfType['rSOC']} >=0, <=1 default 0.85; # (H2 LHV/elec output) eff (includes heat that is provided through electrical heaters)
param SOEC_therm_eff{u in UnitsOfType['rSOC']} <=1 default 0; # (H2 LHV/elec output) eff # Requires Heat (since Methanator is modelled appart) -0.15

param SOEC_power_max_limit_in{u in UnitsOfType['rSOC']} >=0 default 3;
param SOFC_power_max_limit_out{u in UnitsOfType['rSOC']} >=0 default 1;
param SOEC_power_min_limit_in{u in UnitsOfType['rSOC']} >=0 default 0;
param SOFC_power_min_limit_out{u in UnitsOfType['rSOC']} >=0 default 0;

param bigM_rSOC >= 0 default 1e6;

param mol_h_CO2_per_kW_CH4{u in UnitsOfType['rSOC']} >=0 default 4.405796988*1.014890593; # (from Aspen calculations)

#   param rSOC_eff_degradation{u in UnitsOfType['rSOC']} >=0, <=1 default 0.005;#/1000H
#   param rSOC_conv_eff{u in UnitsOfType['rSOC']} >=0, <=rSOC_conv_eff_basis[u] := rSOC_conv_eff_basis[u]-rSOC_eff_degradation[u]*8760*lifetime[u]/2/1000; # (elec output/H2 LHV) eff

var mode_SOFC{u in UnitsOfType['rSOC'], p in Period, t in Time[p]} binary := 0;
var mode_SOEC{u in UnitsOfType['rSOC'], p in Period, t in Time[p]} binary := 0;

subject to SOFC_energy_balance{u in UnitsOfType['rSOC'], p in Period,t in Time[p]}:
    Units_supply['Electricity',u,p,t] =
    SOFC_elec_eff[u]*Units_demand['Hydrogen',u,p,t] +
    SOFC_elec_eff[u]*Units_demand['Biomethane',u,p,t];

subject to SOEC_energy_balance{u in UnitsOfType['rSOC'], p in Period,t in Time[p]}:
    Units_supply['Hydrogen',u,p,t] = SOEC_conv_eff[u]*Units_demand['Electricity',u,p,t];

subject to SOFC_energy_balance_2{u in UnitsOfType['rSOC'], p in Period,t in Time[p]}:
    Units_supply['CO2',u,p,t] <= mol_h_CO2_per_kW_CH4[u]*Units_demand['Biomethane',u,p,t];

#-hot stream heat leaving
subject to SOFC_Usable_heat_computation{h in House,u in UnitsOfType['rSOC'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
    Units_demand['Hydrogen',u,p,t]*SOFC_therm_eff[u] +
    Units_demand['Biomethane',u,p,t]*SOFC_therm_eff[u]
    >= sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];
/*
#-hot stream heat entering in SOEC
subject to SOEC_required_heat_computation{h in House,u in UnitsOfType['rSOC'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hout[st] = 1}:
    -Units_demand['Electricity',u,p,t]*SOEC_therm_eff[u] = sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];
*/

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

/*
# Part load limitations usibg bigM method to allow the electricity flow to be either 0 or at least the minimal threshold
# SOFC mode part-load constraint
subject to SOFC_partload{u in UnitsOfType['rSOC'],p in Period, t in Time[p]}:
    Units_supply['Electricity',u,p,t] = 0
    or Units_supply['Electricity',u,p,t] >= Units_Mult[u] * SOFC_power_min_limit_out[u];

# SOEC mode part-load constraint
subject to SOEC_partload{u in UnitsOfType['rSOC'],p in Period, t in Time[p]}:
    Units_demand['Electricity',u,p,t] = 0
    or Units_demand['Electricity',u,p,t] >= Units_Mult[u] * SOEC_power_min_limit_in[u];
*/