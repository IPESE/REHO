#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Methanator. Produce biomethane (CH4) from a CO2 stream and a H2 stream. These two streams can either be produced locally
# (through electrolysis and carbon capture) or purchased externally if the grids are not constrained. Initial setting of
# grids.csv does not allow for any import/export of H2/CO2. Note that the produced biomethane can be considered as
# Natural Gas and hence be used in other units as such or even sold to the grid.
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param MTR_conv_eff{u in UnitsOfType['Methanator']} >=0, <=1 default 0.8490;
param MTR_power_limit_in{u in UnitsOfType['Methanator']} >=0 default 1;
param MTR_therm_eff_high_T{u in UnitsOfType['Methanator']} >= 0 default 0.2119;
param MTR_therm_eff_mid_T{u in UnitsOfType['Methanator']} >= 0 default 0.0269;
param MTR_therm_eff_low_T{u in UnitsOfType['Methanator']} >= 0 default 0.0534; # including small part of SOEC

param MTR_CO2_mol_h_per_kW_H2{u in UnitsOfType['Methanator']} default 3.721349846; # from Aspen simulations (mol/h of CO2 for 1 kW H2 input)
param MTR_elec_cons_15_bars{u in UnitsOfType['Methanator']} default 0.0149; # Make use of high Pressure CO2 to entrain low P H2 (ejector) for a final pressure of ~15 bars

param bigM_meth >= 0 default 1e6;
subject to MTR_co2_needs_computation{u in UnitsOfType['Methanator'], p in Period, t in Time[p]}:
    Units_demand['CO2',u,p,t] = MTR_CO2_mol_h_per_kW_H2[u]*Units_demand['Hydrogen',u,p,t];

#-hot stream heat leaving
subject to MTR_Usable_heat_computation{h in House,u in UnitsOfType['Methanator'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
    Units_demand['Hydrogen',u,p,t]*(MTR_therm_eff_high_T[u] + MTR_therm_eff_mid_T[u])  >= sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];

subject to MTR_CH4_production{u in UnitsOfType['Methanator'], p in Period,t in Time[p]}:
    Units_supply['Biomethane',u,p,t] = MTR_conv_eff[u]*Units_demand['Hydrogen',u,p,t]; #

subject to MTR_elec_consumption{u in UnitsOfType['Methanator'], p in Period,t in Time[p]}:
    Units_demand['Electricity',u,p,t] = MTR_elec_cons_15_bars[u]*Units_demand['Hydrogen',u,p,t];

# Power limitation
subject to MTR_PL_c1{u in UnitsOfType['Methanator'], p in Period,t in Time[p]}:
    Units_supply['Biomethane',u,p,t] <= Units_Mult[u] * MTR_power_limit_in[u];

#subject to low_T_heat_available_meth{u in UnitsOfType['Methanator'],v in UnitsOfType['rSOC'], p in Period, t in Time[p]}:
#    waste_heat_available[p,t] <= MTR_therm_eff_low_T[u]*Units_demand['Hydrogen',u,p,t] + (1 - mode_SOEC[v,p,t])* bigM_meth;

