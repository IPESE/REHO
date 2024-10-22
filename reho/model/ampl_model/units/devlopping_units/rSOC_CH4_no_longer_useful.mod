#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Reversible Solid Oxide Cells (rSOC_CH4) is a technology that can operate in both modes, either producing electricity from
# various fuels (H2, CH4, ...) or converting excess electricity into molecules, allowing for long-term seasonal storage.
# The rSOC_CH4s are known for their high electrical/conversion efficiencies, thanks to the high operating temperatures (>700 °C)
# and also outputs high quality heat that can be recovered for further electricity production, industrial processes or
# even district heating networks. This is valid in both modes (Fuel cell or Electrolyzer), at different temperatures and
# quantities. The electrolyzer mode can operate at higher current densities, resulting (with the higher voltage due to
# thermodynamic considerations) in a power input 3 times higher than the output SOFC_CH4 power. Typical module sizes would
# be 50 kW fuel cell (=150 kW Electrolyzer).
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param SOFC_CH4_elec_eff{u in UnitsOfType['rSOC_CH4']} >=0, <=1 default 0.6; # (elec output/H2 LHV) eff
param SOFC_CH4_therm_eff{u in UnitsOfType['rSOC_CH4']} >=0, <=1 default 0.3; # (elec output/H2 LHV) eff
param SOEC_CH4_conv_eff{u in UnitsOfType['rSOC_CH4']} >=0, <=1 default 0.85; # (H2 LHV/elec output) eff
param SOEC_CH4_therm_eff{u in UnitsOfType['rSOC_CH4']} >=0, <=1 default 0.1; # (H2 LHV/elec output) efff

param SOEC_CH4_power_limit_in{u in UnitsOfType['rSOC_CH4']} >=0 default 3;
param SOFC_CH4_power_limit_out{u in UnitsOfType['rSOC_CH4']} >=0 default 1;

param mol_h_CO2_per_kW_CH4{u in UnitsOfType['rSOC_CH4']} >=0 default 4.405796988*1.014890593; # (elec output/H2 LHV) eff

#   param rSOC_CH4_eff_degradation{u in UnitsOfType['rSOC_CH4']} >=0, <=1 default 0.005;#/1000H
#   param rSOC_CH4_conv_eff{u in UnitsOfType['rSOC_CH4']} >=0, <=rSOC_CH4_conv_eff_basis[u] := rSOC_CH4_conv_eff_basis[u]-rSOC_CH4_eff_degradation[u]*8760*lifetime[u]/2/1000; # (elec output/H2 LHV) eff

var mode_SOFC_CH4{u in UnitsOfType['rSOC_CH4'], p in Period, t in Time[p]} binary;
var mode_SOEC_CH4{u in UnitsOfType['rSOC_CH4'], p in Period, t in Time[p]} binary;
param M_rSOC_CH4 := 1e12;

subject to SOFC_CH4_energy_balance{u in UnitsOfType['rSOC_CH4'], p in Period,t in Time[p]}:
    Units_supply['Electricity',u,p,t] = SOFC_CH4_elec_eff[u]*Units_demand['Biogas',u,p,t];

subject to SOFC_CH4_energy_balance_2{u in UnitsOfType['rSOC_CH4'], p in Period,t in Time[p]}:
    Units_supply['CO2',u,p,t] = mol_h_CO2_per_kW_CH4[u]*Units_demand['Biogas',u,p,t];

subject to SOEC_CH4_energy_balance{u in UnitsOfType['rSOC_CH4'], p in Period,t in Time[p]}:
    Units_supply['Hydrogen',u,p,t] = SOEC_CH4_conv_eff[u]*Units_demand['Electricity',u,p,t];

#-hot stream heat leaving
subject to SOFC_CH4_Usable_heat_computation{h in House,u in UnitsOfType['rSOC_CH4'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
    Units_demand['Biogas',u,p,t]*SOFC_CH4_therm_eff[u] +
    Units_demand['Electricity',u,p,t]*SOEC_CH4_therm_eff[u]
    >= sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];

# Power limitation
subject to SOFC_CH4_mult{u in UnitsOfType['rSOC_CH4'],p in Period, t in Time[p]}:
    Units_supply['Electricity',u,p,t] <= Units_Mult[u]*SOFC_CH4_power_limit_out[u];

subject to SOEC_CH4_mult{u in UnitsOfType['rSOC_CH4'],p in Period, t in Time[p]}:
    Units_demand['Electricity',u,p,t] <= Units_Mult[u]*SOEC_CH4_power_limit_in[u];

subject to SOFC_mode_supply_link{u in UnitsOfType['rSOC_CH4'], p in Period, t in Time[p]}:
    Units_supply['Electricity',u,p,t] <= mode_SOFC_CH4[u,p,t] * M_rSOC_CH4;

subject to SOEC_mode_demand_link{u in UnitsOfType['rSOC_CH4'], p in Period, t in Time[p]}:
    Units_demand['Electricity',u,p,t] <= mode_SOEC_CH4[u,p,t] * M_rSOC_CH4;

subject to no_2_modes_simultaneously_CH4{u in UnitsOfType['rSOC_CH4'], p in Period, t in Time[p]}:
    mode_SOFC_CH4[u,p,t] + mode_SOEC_CH4[u,p,t] <= 1;
