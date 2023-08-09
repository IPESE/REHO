
# ----------------------------------------- PARAMETERS ---------------------------------------
param dt_min default 1;
param DHN_efficiency_in{u in UnitsOfType['DHN_hex']}  := if min{h in House} Th_supply_0[h] + dt_min < T_DHN_supply_cst and min{h in House} Th_return_0[h] + dt_min < T_DHN_return_cst then 0.95 else 0;
param DHN_efficiency_out{u in UnitsOfType['DHN_hex']}  := if min{h in House} Tc_supply_0[h] >= T_DHN_return_cst + dt_min and min{h in House} Tc_return_0[h] >= T_DHN_supply_cst + dt_min then 1.0 else 0;

param T_m_out{h in House}  := (Tc_supply_0[h] + Tc_return_0[h])/2 - (T_DHN_supply_cst + T_DHN_return_cst)/2;
param T_m_in{h in House}  :=  (T_DHN_supply_cst + T_DHN_return_cst)/2 - (Th_supply_0[h] + Th_return_0[h])/2;

param U_hex default 1; # [kW / m2K], https://sistemas.eel.usp.br/docentes/arquivos/5817712/LOQ4086/saari__heat_exchanger_dimensioning.pdf


# ---------------------------------------- CONSTRAINTS ---------------------------------------
# direct heating
subject to HEX_heating1{h in House,u in {'DHN_hex_in_'&h},p in Period,t in Time[p]}:
	Units_demand['Heat',u,p,t]/(U_hex * T_m_in[h])  <= Units_Mult[u];	

subject to HEX_heating2{h in House,u in {'DHN_hex_in_'&h},p in Period,t in Time[p]}:
	Units_demand['Heat',u,p,t] * DHN_efficiency_in[u] = sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t]; 	#kW

subject to HEX_heating3{h in House, u in {'DHN_hex_in_'&h}, p in Period,t in Time[p]}:
	Units_demand['Heat',u,p,t] <= 1e4 *  DHN_efficiency_in[u];	


# direct cooling
subject to HEX_cooling1{h in House, u in {'DHN_hex_out_'&h}, p in Period,t in Time[p]}:
	Units_supply['Heat',u,p,t]/(U_hex * T_m_out[h])  <= Units_Mult[u];	

subject to HEX_cooling2{h in House, u in {'DHN_hex_out_'&h}, p in Period,t in Time[p]}:
	Units_supply['Heat',u,p,t] * DHN_efficiency_out[u] = sum{st in StreamsOfUnit[u],se in ServicesOfStream[st]} Streams_Q[se,st,p,t];	

subject to HEX_cooling3{h in House, u in {'DHN_hex_out_'&h}, p in Period,t in Time[p]}:
	Units_supply['Heat',u,p,t] <= 1e4 *  DHN_efficiency_out[u];	
