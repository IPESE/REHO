######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# District heating network - Sizing for connection between building and the DHN infrastructure
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param DHN_partload_max_in{u in UnitsOfType['DHN_pipes']} default 1;

subject to DHN_c1{h in House, u in {'DHN_pipes_'&h}, p in Period,t in Time[p]}:
	Grid_supply['Heat',h,p,t]  <= Units_Mult[u] * DHN_partload_max_in[u];	

subject to DHN_c2{h in House, u in {'DHN_pipes_'&h}, p in Period,t in Time[p]}:
	Grid_demand['Heat',h,p,t]  <= Units_Mult[u] * DHN_partload_max_in[u];	
