#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Methanator. Produce biomethane (CH4) from a CO2 stream and a H2 stream. These two streams can either be produced locally
# (through electrolysis and carbon capture) or purchased externally if the grids are not constrained. Initial setting of
# grids.csv does not allow for any import/export of H2/CO2. Note that the produced biomethane can be considered as
# Natural Gas and hence be used in other units as such or even sold to the grid.
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param MTZ_conv_eff_basis{u in UnitsOfType['Methanator']} >=0, <=1 default 0.832255725;
param MTZ_power_limit_in_basis{u in UnitsOfType['Methanator']} >=0 default 1;
param MTZ_CO2_mol_h_per_kW_H2{u in UnitsOfType['Methanator']} default 3.721349846; # from Aspen simulations (mol/h of CO2 for 1 kW H2 input)
param MTZ_elec_cons_7_bars{u in UnitsOfType['Methanator']} default 0.01322; # from Aspen simulations (electrical input (up to 7 bars) Methanator)

param equivalency_bio_to_NG >= 0 default 1;

subject to MTZ_co2_needs_computation{u in UnitsOfType['Methanator'], p in Period, t in Time[p]}:
    Units_demand['CO2',u,p,t] = MTZ_CO2_mol_h_per_kW_H2[u]*Units_demand['Hydrogen',u,p,t];

#-hot stream heat leaving
subject to MTZ_Usable_heat_computation{h in House,u in UnitsOfType['Methanator'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]:Streams_Hin[st] = 1}:
    Units_demand['Hydrogen',u,p,t]*(1-MTZ_conv_eff_basis[u])*0.9 >= sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t];

subject to MTZ_CH4_production{u in UnitsOfType['Methanator'], p in Period,t in Time[p]}:
    Units_supply['Biomethane',u,p,t] + Units_supply['NaturalGas',u,p,t] = MTZ_conv_eff_basis[u]*Units_demand['Hydrogen',u,p,t];

subject to MTZ_elec_consumption{u in UnitsOfType['Methanator'], p in Period,t in Time[p]}:
    Units_demand['Electricity',u,p,t] = MTZ_elec_cons_7_bars[u]*Units_demand['Hydrogen',u,p,t];

# Power limitation
subject to MTZ_PL_c1{u in UnitsOfType['Methanator'], p in Period,t in Time[p]}:
    Units_supply['Biomethane',u,p,t] <= Units_Mult[u]*MTZ_power_limit_in_basis[u];
