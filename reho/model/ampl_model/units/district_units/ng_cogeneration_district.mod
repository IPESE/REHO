######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Natural gas cogeneration (district)
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param NG_Cogeneration_partload_max{u in UnitsOfType['NG_Cogeneration']} default 1;
param NG_Cogeneration_partload_min{u in UnitsOfType['NG_Cogeneration']} default 0.5;
param NG_Cogeneration_E_efficiency_nom{u in UnitsOfType['NG_Cogeneration']} default 0.27;
param NG_Cogeneration_Q_efficiency_nom{u in UnitsOfType['NG_Cogeneration']} default 0.59;

subject to NG_Cogeneration_energy_balance{h in House,u in UnitsOfType['NG_Cogeneration'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] 	= NG_Cogeneration_E_efficiency_nom[u]*Units_demand['NaturalGas',u,p,t];

subject to NG_Cogeneration_EB_c2{u in UnitsOfType['NG_Cogeneration'],p in Period,t in Time[p]}:
Units_supply['Heat',u,p,t] = NG_Cogeneration_Q_efficiency_nom[u]*Units_demand['NaturalGas',u,p,t];

subject to NG_Cogeneration_c1{h in House,u in UnitsOfType['NG_Cogeneration'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] <= Units_Mult[u]*NG_Cogeneration_partload_max[u];

subject to NG_Cogeneration_c2{h in House,u in UnitsOfType['NG_Cogeneration'] inter UnitsOfHouse[h],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t] >= Units_Mult[u]*NG_Cogeneration_partload_min[u];
