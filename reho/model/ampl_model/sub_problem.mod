######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# SETS
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#-MAIN SETS
set LayerTypes; 		# Type of layer (HeatCascade, MassBalance, ...)
set Layers;				# Set of layers
set UnitTypes;			# Type of unit
set Units;				# Set of units
set House ordered;		# Set of houses (clusters)
set Services;			# Set of services (2nd clusters)
set Period;				# Set of periods (days)
set PeriodStandard;		# Set of standard periods (not extreme) 
set PeriodExtreme := {Period diff PeriodStandard};
set HP_Tsupply default {35,45,55};
set ActorObjective;																#-

#-TIME SETS
param TimeStart default 1;
param TimeEnd{p in Period};
set Time{p in Period} := {TimeStart .. TimeEnd[p]} ordered;

#-INDEX SETS (useful for inter-period energy balance appart from the extreme periods)
set Year := {1..8760} circular;
param PeriodOfYear{y in Year} default 1;
param TimeOfYear{y in Year} default 1;

#-SUB-SETS
#-Units and layers
set UnitsOfType{UnitTypes} within Units;
set LayersOfType{LayerTypes} within Layers;

set UnitsOfHouse{House} within Units;
set UnitsOfDistrict within Units default {};
set UnitsOfService{Services} within Units;
set UnitsOfLayer{Layers} within Units;

#-House
set HousesOfLayer{Layers} within House;

#-Streams
set StreamsOfUnit{u in Units} default {};
set StreamsOfBuilding{h in House} default {};
set StreamsOfHouse{h in House} := setof{u in UnitsOfHouse[h],su in StreamsOfUnit[u]} su union StreamsOfBuilding[h];
set Streams := setof{h in House, st in StreamsOfHouse[h]} st;

set StreamsOfService{se in Services} within Streams := (if (se='SH' or se='Cooling')  then setof{h in House,u in UnitsOfService[se],s in StreamsOfUnit[u] union StreamsOfBuilding[h]} s else setof{u in UnitsOfService[se],s in StreamsOfUnit[u]} s);
set ServicesOfStream{s in Streams} within Services := setof{se in Services,sl in StreamsOfService[se]: s = sl} se;

######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# GENERAL PARAMETERS
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#-STANDARD PHYSICAL VALUES
param LHV_ng := 50018;						#kJ/kg
param LKV_ng := 51757;						#kJ/kg
param cp_water_kj := 4.18;					#KJ/kg K	
param rho_water := 1;					#kg/L
param Pi := 4 * atan(1);					#-

#-TEMPORAL DATA
param T_ext{p in Period,t in Time[p]};		#deg C
param Irr{p in Period,t in Time[p]};	#W/m2

#-THERMAL STREAMS
param T_DHN_supply_cst default 80; 			#deg C
param T_DHN_return_cst default 60; 			#deg C
param T_DHN_supply{p in Period, t in Time[p]} default T_DHN_supply_cst; #deg C
param T_DHN_return{p in Period, t in Time[p]} default T_DHN_return_cst; #deg C

param Streams_Tin{s in Streams,p in Period,t in Time[p]} default 90; 	#deg C
param Streams_Tout{s in Streams,p in Period,t in Time[p]} default 80;  	#deg C
param Streams_Hin{s in Streams}	default 0; 								#kJ/kg
param Streams_Hout{s in Streams}default 0; 								#kJ/kg
param Streams_Mcp{s in Streams,p in Period,t in Time[p]}:=  
	if Streams_Tin[s,p,t]=Streams_Tout[s,p,t] then 
		0 
	else  
		(Streams_Hin[s]-Streams_Hout[s])/(Streams_Tin[s,p,t]-Streams_Tout[s,p,t])
	; 																	#kJ/kg K

######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# UNITS
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

param Units_Fmin{u in Units} default 0;
param Units_Fmax{u in Units} default 0;
param Units_Ext{u in Units} default 0;

var Units_Mult{u in Units} <= Units_Fmax[u];
var Units_Use{u in Units} binary, default 0;

var Units_Use_Ext{u in Units} binary, default 1;
var Units_Buy{u in Units} binary, default 0;

subject to Units_sizing_c1{u in Units}:
Units_Mult[u]-Units_Use_Ext[u]*Units_Ext[u] >= Units_Buy[u]*Units_Fmin[u];

subject to Units_sizing_c2{u in Units}:
Units_Mult[u]-Units_Use_Ext[u]*Units_Ext[u] <= Units_Buy[u]*(Units_Fmax[u]-Units_Ext[u]);

subject to Units_Use_constraint_c1{u in Units}:
Units_Use[u]*Units_Fmax[u]>=Units_Mult[u];

subject to Units_Use_constraint_c2{u in Units}:
Units_Use[u]*Units_Fmin[u]<=Units_Mult[u];

######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# MASS BALANCES
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#-Filtering Layers and selecting only layers of type "ResourceBalance"
set ResourceBalances := if (exists{t in LayerTypes} t = 'ResourceBalance') then ({l in LayersOfType["ResourceBalance"]}) else ({});

#-Definition of units per layer and cluster  
set MB_Units{l in ResourceBalances,h in HousesOfLayer[l]} := UnitsOfLayer[l] inter UnitsOfHouse[h];

#-Defining links between units
set MB_links:= {l in ResourceBalances,h in HousesOfLayer[l],i in MB_Units[l,h],j in MB_Units[l,h],p in Period,t in Time[p]};

#-Each unit can have an input and an output flowrate
param Units_flowrate_in{l in ResourceBalances, u in UnitsOfLayer[l]}  >=0 default 0;
param Units_flowrate_out{l in ResourceBalances, u in UnitsOfLayer[l]} >=0 default 0;
param Domestic_electricity{h in House, p in Period, t in Time[p]} >= 0 default 0;

var Units_supply{l in ResourceBalances, u in UnitsOfLayer[l], p in Period, t in Time[p]} >= 0, <= Units_flowrate_out[l,u]; 
var Units_demand{l in ResourceBalances, u in UnitsOfLayer[l], p in Period, t in Time[p]} >= 0, <= Units_flowrate_in[l,u];
var Units_curtailment{l in ResourceBalances, u in UnitsOfLayer[l] , p in Period, t in Time[p]} >= 0, <= Units_flowrate_out[l,u]; 

var Grid_supply{l in ResourceBalances, h in HousesOfLayer[l], p in Period, t in Time[p]} >= 0, <= 1e8; 
var Grid_demand{l in ResourceBalances, h in HousesOfLayer[l], p in Period, t in Time[p]} >= 0, <= 1e8;

var Network_supply{l in ResourceBalances, p in Period, t in Time[p]} >= 0, <= 1e8; 
var Network_demand{l in ResourceBalances, p in Period, t in Time[p]} >= 0, <= 1e8; 

subject to MB_electricity{h in House, p in Period, t in Time[p]}:
	Grid_supply['Electricity',h,p,t] + sum {i in MB_Units['Electricity',h]} Units_supply['Electricity',i,p,t] = Grid_demand['Electricity',h,p,t] + Domestic_electricity[h,p,t] + sum {j in MB_Units['Electricity',h]} Units_demand['Electricity',j,p,t];

subject to MB_c1{h in House, l in ResourceBalances diff {'Electricity'}, hl in HousesOfLayer[l], p in Period, t in Time[p]: h=hl}:
	Grid_supply[l,h,p,t] + sum {i in MB_Units[l,h]} Units_supply[l,i,p,t] = Grid_demand[l,h,p,t] + sum {j in MB_Units[l,h]} Units_demand[l,j,p,t];

subject to MB_c2{l in ResourceBalances,p in Period,t in Time[p]}:
	 Network_demand[l,p,t] + sum{i in HousesOfLayer[l]}(Grid_supply[l,i,p,t]) -sum {b in UnitsOfDistrict inter UnitsOfLayer[l]} Units_supply[l,b,p,t] =
	  Network_supply[l,p,t] + sum{j in HousesOfLayer[l]}(Grid_demand[l,j,p,t]) -sum {r in UnitsOfDistrict inter UnitsOfLayer[l]} Units_demand[l,r,p,t] ;

######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# HEAT CASCADE
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#--------------------------------------------------------------------------------------------------------------------#
#-STREAMS
#--------------------------------------------------------------------------------------------------------------------#

#--Hot streams
set HC_Hot within {st in Streams} := {s in Streams: Streams_Hout[s] < Streams_Hin[s]};
set HC_Hot_loc {h in House} within {st in Streams}:= {s in HC_Hot : s in StreamsOfHouse[h]};
	check {h in House: card(Streams) > 0}: card(HC_Hot_loc[h]) > 0;
set HC_Hot_loc_SQ {h in House,sq in Services} within {st in Streams}:= ({s in HC_Hot_loc[h] : s in StreamsOfService[sq]});
	check {h in House,sq in Services: card(Streams) > 0}: card(HC_Hot_loc_SQ[h,sq]) > 0;

#--Cold streams 
set HC_Cold within {st in Streams} := {s in Streams: Streams_Hout[s]>Streams_Hin[s]};
set HC_Cold_loc {h in House} within {st in Streams}:= {s in HC_Cold : s in StreamsOfHouse[h]};
	check {h in House: card(Streams) > 0}: card(HC_Cold_loc[h]) > 0;
set HC_Cold_loc_SQ {h in House,sq in Services} within {st in Streams}:= ({s in HC_Cold_loc[h] : s in StreamsOfService[sq]});
	check {h in House,sq in Services: card(Streams) > 0}: card(HC_Cold_loc_SQ[h,sq]) > 0;

param dTmin{Streams} default 0;
param Streams_Tin_corr{s in Streams,p in Period,t in Time[p]} 	:= if (s in HC_Hot) then Streams_Tin[s,p,t] - dTmin[s]/2 else Streams_Tin[s,p,t] + dTmin[s]/2;
param Streams_Tout_corr{s in Streams,p in Period,t in Time[p]} 	:= if (s in HC_Hot) then Streams_Tout[s,p,t] - dTmin[s]/2 else Streams_Tout[s,p,t] + dTmin[s]/2;

var HC_Streams_Mult{sq in Services,s in StreamsOfService[sq],p in Period,t in Time[p]}>=0,<=1e8;
var Streams_Q{sq in Services,s in StreamsOfService[sq],p in Period,t in Time[p]}>=0,<=1e8;

subject to Streams_Q_def{sq in Services,s in StreamsOfService[sq],p in Period,t in Time[p]}:
Streams_Q[sq,s,p,t] = Streams_Mcp[s,p,t] * HC_Streams_Mult[sq,s,p,t] * abs(Streams_Tin[s,p,t] - Streams_Tout[s,p,t]);

#--------------------------------------------------------------------------------------------------------------------#
#-HEAT CASCADE (refer to Stadler 2019, p.23)
#--------------------------------------------------------------------------------------------------------------------#
set HC_TempIntervals_SQ{h in House,sq in Services,p in Period,t in Time[p]} ordered by Reals :=
setof {s in HC_Hot_loc_SQ[h,sq] union HC_Cold_loc_SQ[h,sq]} Streams_Tin_corr[s,p,t] union 
setof {s in HC_Hot_loc_SQ[h,sq] union HC_Cold_loc_SQ[h,sq]} Streams_Tout_corr[s,p,t]; 

param Min_T{h in House,sq in Services,p in Period,t in Time[p]} := min{k in HC_TempIntervals_SQ[h,sq,p,t]} k;
param Max_T{h in House,sq in Services,p in Period,t in Time[p]} := max{k in HC_TempIntervals_SQ[h,sq,p,t]} k; 
param epsilon := 1e-5;

var HC_Rk{h in House,sq in Services, p in Period,t in Time[p],k in HC_TempIntervals_SQ[h,sq,p,t]}>=0;

subject to HC_heat_cascade{h in House,sq in Services, p in Period,t in Time[p],k in HC_TempIntervals_SQ[h,sq,p,t]}:
sum{st in HC_Hot_loc_SQ[h,sq]:Streams_Tout_corr[st,p,t]>= k + epsilon} 
     (Streams_Mcp[st,p,t]*HC_Streams_Mult[sq,st,p,t]*(Streams_Tin_corr[st,p,t]-Streams_Tout_corr[st,p,t])) -
	 
sum{st in HC_Cold_loc_SQ[h,sq]:Streams_Tin_corr[st,p,t]>= k + epsilon} 
    (Streams_Mcp[st,p,t]*HC_Streams_Mult[sq,st,p,t]*(Streams_Tout_corr[st,p,t]-Streams_Tin_corr[st,p,t])) +
	
sum{st in HC_Hot_loc_SQ[h,sq]:Streams_Tout_corr[st,p,t]<= k and Streams_Tin_corr[st,p,t]>= k + epsilon}
     (Streams_Mcp[st,p,t]*HC_Streams_Mult[sq,st,p,t]*(Streams_Tin_corr[st,p,t] - k)) -
	 
sum{st in HC_Cold_loc_SQ[h,sq]:Streams_Tin_corr[st,p,t]<= k and Streams_Tout_corr[st,p,t]>= k + epsilon}
    (Streams_Mcp[st,p,t]*HC_Streams_Mult[sq,st,p,t]*(Streams_Tout_corr[st,p,t] - k ))
	
-HC_Rk[h,sq,p,t,k]=0;

subject to HC_lowerbound_Rk{h in House,sq in Services,p in Period,t in Time[p],k in HC_TempIntervals_SQ[h,sq,p,t]:k=Min_T[h,sq,p,t]}:
HC_Rk[h,sq,p,t,k] = 0;

subject to HC_upperbound_Rk{h in House,sq in Services,p in Period,t in Time[p],k in HC_TempIntervals_SQ[h,sq,p,t]:k=Max_T[h,sq,p,t]}:
HC_Rk[h,sq,p,t,k] = 0;

#--No heat from hot streams below minimum input temperature
subject to HC_lowerbound_Balance{h in House,sq in Services,p in Period,t in Time[p],k in HC_TempIntervals_SQ[h,sq,p,t]: k=Min_T[h,sq,p,t]}:
sum{st in HC_Hot_loc_SQ[h,sq]:Streams_Tout_corr[st,p,t] <= k-epsilon} (Streams_Mcp[st,p,t]*HC_Streams_Mult[st,sq,p,t]*(k - Streams_Tout_corr[st,p,t])) = 0;

#--No heat from cold streams above maximum input temperature
subject to HC_upperbound_Balance{h in House,sq in Services,p in Period,t in Time[p],k in HC_TempIntervals_SQ[h,sq,p,t]: k=Max_T[h,sq,p,t]}:
sum{st in HC_Cold_loc_SQ[h,sq]: Streams_Tout_corr[st,p,t]>=k+epsilon} (Streams_Mcp[st,p,t]*HC_Streams_Mult[st,sq,p,t]*(Streams_Tout_corr[st,p,t] - k)) = 0;

# Transformer additional capacity
set ReinforcementOfNetwork{ResourceBalances} default {};
var Network_capacity{l in ResourceBalances} in ReinforcementOfNetwork[l];
var Use_Network_capacity{l in ResourceBalances} binary;
param Cost_network_inv1{l in ResourceBalances}>=0 default 0;
param Cost_network_inv2{l in ResourceBalances}>=0 default 0;
param GWP_network_1{l in ResourceBalances} default 0;
param GWP_network_2{l in ResourceBalances} default 0;
param Network_ext{l in ResourceBalances} default 1e8;
param Network_lifetime{l in ResourceBalances} default 20;

# Lines additional capacities
set ReinforcementOfLine{ResourceBalances} default {};
var LineCapacity{l in ResourceBalances, hl in HousesOfLayer[l]} in ReinforcementOfLine[l];
var Use_Line_capacity{l in ResourceBalances, hl in HousesOfLayer[l]} binary;
param Cost_line_inv1{l in ResourceBalances} default 0;
param Cost_line_inv2{l in ResourceBalances} default 0; # [CHF/kW/m]
param Line_Length{h in House,l in ResourceBalances} default 10;
param GWP_line_1{l in ResourceBalances} default 0;
param GWP_line_2{l in ResourceBalances} default 0;
param Line_ext{h in House, l in ResourceBalances} default 1e8;
param Line_lifetime{h in House, l in ResourceBalances} default 20;

######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Emissions
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#--------------------------------------------------------------------------------------------------------------------#
#-TIME FREQUENCIES
#--------------------------------------------------------------------------------------------------------------------#
param dt{Period} default 1;		#h
param dp{Period} default 1;		#days

param lifetime{u in Units} default 20;
param n_years_ins default 50;

param GWP_supply_cst{l in ResourceBalances} default 0.100;
param GWP_demand_cst{l in ResourceBalances} default 0.0; 						#-
param GWP_supply{l in ResourceBalances,p in Period,t in Time[p]} default GWP_supply_cst[l];
param GWP_demand{l in ResourceBalances,p in Period,t in Time[p]} default GWP_demand_cst[l];											# kgCO2/unit
param GWP_unit1{u in Units} default 0;
param GWP_unit2{u in Units} default 0;
param GWP_ins{h in House} default 0;
var GWP_house_op{h in House};
var GWP_op;
var GWP_Unit_constr{u in Units} >= 0;
var GWP_house_constr{h in House} >=0;
var GWP_constr>=0;

subject to Annual_CO2_operation_house{h in House}: 
GWP_house_op[h] = sum{l in ResourceBalances,p in PeriodStandard,t in Time[p]} (GWP_supply[l,p,t]*Grid_supply[l,h,p,t]-GWP_demand[l,p,t]*Grid_demand[l,h,p,t]) *dp[p]*dt[p];

subject to Annual_CO2_operation:
GWP_op = sum{l in ResourceBalances, p in PeriodStandard,t in Time[p]}(GWP_supply[l,p,t]*Network_supply[l,p,t]-GWP_demand[l,p,t]*Network_demand[l,p,t]) *dp[p]*dt[p];

subject to Annual_CO2_construction_unit{u in Units}:
GWP_Unit_constr[u] = (Units_Buy[u]*GWP_unit1[u] + (Units_Mult[u]-Units_Use_Ext[u]*Units_Ext[u])*GWP_unit2[u])/lifetime[u];

subject to Annual_CO2_construction_house{h in House}:
GWP_house_constr[h] = sum{u in UnitsOfHouse[h]}(GWP_Unit_constr[u]) + GWP_ins[h]/n_years_ins +
					sum{l in ResourceBalances: h in HousesOfLayer[l]}(GWP_line_1[l]*Use_Line_capacity[l,h]+GWP_line_2[l]*(LineCapacity[l,h]-Line_ext[h,l] * (1-Use_Line_capacity[l,h]))*Line_Length[h,l]/Line_lifetime[h,l]);

subject to Annual_CO2_construction:
GWP_constr = sum{u in Units} (GWP_Unit_constr[u]) + sum{h in House} (GWP_ins[h])/n_years_ins+
			sum{l in ResourceBalances, h in HousesOfLayer[l]}(GWP_line_1[l]*Use_Line_capacity[l,h]+GWP_line_2[l]*(LineCapacity[l,h]-Line_ext[h,l] * (1-Use_Line_capacity[l,h]))*Line_Length[h,l]/Line_lifetime[h,l]); 


######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# COSTS
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#--------------------------------------------------------------------------------------------------------------------#
#-CAPITAL EXPENSES
#--------------------------------------------------------------------------------------------------------------------#
param ERA{h in House} default 200;											#m2			: Energy reference area
param n_years default 25;
param i_rate default 0.02;
param tau := i_rate*(1+i_rate)^n_years/(((1+i_rate)^n_years)-1);
param tau_ins := i_rate*(1+i_rate)^n_years_ins/(((1+i_rate)^n_years_ins)-1);

param Costs_House_limit{h in House} default 0;						# CHF/yr
param Cost_inv1{u in Units} default 0;								# CHF
param Cost_inv2{u in Units} default 0;								# CHF/...
param Costs_ins{h in House} default 0;
param Costs_House_upfront_m2 default 7759;
param Costs_House_upfront{h in House} := ERA[h]* Costs_House_upfront_m2;
param Costs_House_yearly{h in House} := Costs_House_upfront[h]/100 + Costs_House_upfront[h] * i_rate * (0.13/(1-(1+i_rate)^(-15)) + 0.67/(1-(1+i_rate)^(-70))) - Costs_House_upfront[h] * (1/15+1/70);

var Costs_Unit_inv{u in Units} >= 0;
var Costs_Unit_rep{u in Units} >= 0;
var Costs_House_inv{h in House} >= Costs_House_limit[h];
var Costs_House_rep{h in House} >= Costs_House_limit[h];
var Costs_inv >= 0;
var Costs_rep >= 0;

subject to line_additional_capacity_c1{l in ResourceBalances,hl in HousesOfLayer[l]}:
Use_Line_capacity[l,hl] * (max {i in ReinforcementOfLine[l]} i)>= LineCapacity[l,hl]-Line_ext[hl,l];

subject to line_additional_capacity_c2{l in ResourceBalances,hl in HousesOfLayer[l]}:
LineCapacity[l,hl]>=Line_ext[hl,l];

subject to Costs_Unit_capex{u in Units}:
Costs_Unit_inv[u] = Units_Buy[u]*Cost_inv1[u] + (Units_Mult[u]-Units_Use_Ext[u]*Units_Ext[u])*Cost_inv2[u];

subject to Costs_House_capex{h in House}:
Costs_House_inv[h] = sum{u in UnitsOfHouse[h]}(Costs_Unit_inv[u]) + Costs_ins[h] * tau_ins / tau+
					sum{l in ResourceBalances: h in HousesOfLayer[l]}(Cost_line_inv1[l]*Use_Line_capacity[l,h]+Cost_line_inv2[l]*(LineCapacity[l,h]-Line_ext[h,l] * (1-Use_Line_capacity[l,h]))*Line_Length[h,l]);

subject to Costs_Unit_replacement{u in Units}:
Costs_Unit_rep[u] = sum{n_rep in 1..(n_years/lifetime[u])-1 by 1}( (1/(1 + i_rate))^(n_rep*lifetime[u])*Costs_Unit_inv[u] );

subject to Costs_House_replacement{h in House}:
Costs_House_rep[h] = sum{u in UnitsOfHouse[h],n_rep in 1..(n_years/lifetime[u])-1 by 1}( (1/(1 + i_rate))^(n_rep*lifetime[u])*Costs_Unit_inv[u] );

subject to Costs_Grid_supply:
Costs_inv =  sum{u in Units}(Costs_Unit_inv[u]) + sum{h in House}(Costs_ins[h]) * tau_ins / tau + 
			sum{l in ResourceBalances, h in HousesOfLayer[l]} (Cost_line_inv1[l]*Use_Line_capacity[l,h]+Cost_line_inv2[l]*(LineCapacity[l,h]-Line_ext[h,l] * (1-Use_Line_capacity[l,h]))*Line_Length[h,l]);#+ sum{l in ResourceBalances} (Cost_network_inv1[l]*Use_Network_capacity[l]+Cost_network_inv2[l] * (Network_capacity[l]-Network_ext[l] * (1- Use_Network_capacity[l]));

subject to Costs_replacement:
Costs_rep =  sum{u in Units} Costs_Unit_rep[u];

#--------------------------------------------------------------------------------------------------------------------#
#-OPERATING EXPENSES
#--------------------------------------------------------------------------------------------------------------------#
param Cost_demand_cst{l in ResourceBalances};	# CHF/kWh
param Cost_supply_cst{l in ResourceBalances};	# CHF/kWh

param Cost_demand{h in House,l in ResourceBalances,p in Period,t in Time[p]} default Cost_demand_cst[l];
param Cost_supply{h in House,l in ResourceBalances,p in Period,t in Time[p]} default Cost_supply_cst[l];
param Cost_demand_network{l in ResourceBalances,p in Period,t in Time[p]} default Cost_demand_cst[l];
param Cost_supply_network{l in ResourceBalances,p in Period,t in Time[p]} default Cost_supply_cst[l];

var Costs_House_op{h in House};
var Costs_op;

subject to Costs_house_opex{h in House}:
Costs_House_op[h] = sum{l in ResourceBalances,p in PeriodStandard,t in Time[p]}( (Cost_supply[h,l,p,t]*Grid_supply[l,h,p,t] - Cost_demand[h,l,p,t]*Grid_demand[l,h,p,t])*dp[p]*dt[p]);

subject to Costs_opex:
Costs_op = sum{l in ResourceBalances,p in PeriodStandard,t in Time[p]}( (Cost_supply_network[l,p,t]*Network_supply[l,p,t] - Cost_demand_network[l,p,t]*Network_demand[l,p,t])*dp[p]*dt[p]);

######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# BUILDING MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#--------------------------------------------------------------------------------------------------------------------#
#-SINGLE STATE FIRST ORDER MODEL
#--------------------------------------------------------------------------------------------------------------------#
param HeatCapacity{h in House} default 120;									#Wh/K m2	: Heat capacity
param U_h{h in House} default 0.002;										#kW/K m2	: Hot total thermal transfer coefficient

param Cooling{h in House} binary, default 0;							    #-			: Binary parameter to enable cooling or not
param SolarRoofArea{h in House} default ERA[h]/3;							#m2 		: Roof area available for solar

param T_comfort_min_0{h in House} default 20;											#deg C		: Reference lower comfort bound
param T_comfort_min{h in House,p in Period,t in Time[p]} default T_comfort_min_0[h];	#deg C		: Time dependent lower comfort bound
param T_comfort_max_0{h in House} default 25;											#deg C		: Reference upper comfort bound
param T_penality{h in House} default 3;													#CHF/C hr	: Comfort Penality costs
param T_inf_limit{h in House} default 5;												#deg C		: Maximum delta of cold temperature acceptable
param T_sup_limit{h in House} default 10;												#deg C		: Maximum delta of hot temperature acceptable

param HeatGains{h in House,p in Period,t in Time[p]}>= 0, default 0;	            	#kW : Internal heat gains
param SolarGains{h in House,p in Period,t in Time[p]} >= 0, default 0;              	#kW	: Solar heat gains

var Costs_House_cft{h in House} >= 0;										        	#CHF/hr
var T_in{h in House,p in Period,t in Time[p]} >= 0;							        	#deg C
var T_inf{h in House,p in PeriodStandard,t in Time[p]} >= 0, <= T_inf_limit[h];			#deg C
var T_sup{h in House,p in PeriodStandard,t in Time[p]} >= 0, <= T_sup_limit[h];			#deg C
var House_Q_heating{h in House,p in Period,t in Time[p]} >= 0;				        	#kW
var House_Q_cooling{h in House,p in Period,t in Time[p]} >= 0;				        	#kW

subject to House_Penality_inf{h in House,p in PeriodStandard,t in Time[p]}:
T_inf[h,p,t] >= T_comfort_min[h,p,t] - T_in[h,p,t];

subject to House_Penality_sup{h in House,p in PeriodStandard,t in Time[p]}:
T_sup[h,p,t] >= Cooling[h]*(T_in[h,p,t] - T_comfort_max_0[h]);

subject to House_Comfort_c1{h in House}:
Costs_House_cft[h] = sum{p in PeriodStandard,t in Time[p]} T_penality[h]*(T_inf[h,p,t] + T_sup[h,p,t])*dp[p]*dt[p];	#CHF/yr

#--------------------------------------------------------------------------------------------------------------------#
#-HEATING CURVE TEMPERATURE DISCRETIZATION
#--------------------------------------------------------------------------------------------------------------------#

#-Design parameters
param Tc_out_0 default 35;																																#deg C	: Warm nominal ambient temperature
param Th_out_0 default if card(Period) > 1 then T_ext[card(Period)-1,1] else -6;															#deg C	: Cold nominal ambient temperature
param Tc_supply_0{h in House} default 12;																												#deg C	: Warm nominal supply temperature
param Th_supply_0{h in House} default 65;																												#deg C	: Cold nominal supply temperature
param Tc_return_0{h in House} default 17;																												#deg C	: Warm nominal return temperature
param Th_return_0{h in House} default 50;																												#deg C	: Cold nominal return temperature
param Th_threshold{h in House} default 16;																												#deg C																																																						#m2
param Qc_0{h in House} 		:= U_h[h]*ERA[h]*(Tc_out_0-T_comfort_min_0[h]);																						#kW
param Qh_0{h in House} 		:= U_h[h]*ERA[h]*(T_comfort_min_0[h]-Th_out_0);																						#kW
param LMTDc_0{h in House}	:= ((T_comfort_min_0[h]-Tc_supply_0[h])-(T_comfort_min_0[h]-Tc_return_0[h]))/(log(T_comfort_min_0[h]-Tc_supply_0[h])-log(T_comfort_min_0[h]-Tc_return_0[h]));	#deg C
param LMTDh_0{h in House}	:= ((Th_supply_0[h]-T_comfort_min_0[h])-(Th_return_0[h]-T_comfort_min_0[h]))/(log(Th_supply_0[h]-T_comfort_min_0[h])-log(Th_return_0[h]-T_comfort_min_0[h]));	#deg C
param UAc_0{h in House}  	:= Qc_0[h]/LMTDc_0[h];																										#kW/K
param UAh_0{h in House}  	:= Qh_0[h]/LMTDh_0[h];																										#kW/K
param Mcp_0c{h in House} 	:= Qc_0[h]/(Tc_return_0[h]-Tc_supply_0[h]);																					#kW/K
param Mcp_0h{h in House} 	:= Qh_0[h]/(Th_supply_0[h]-Th_return_0[h]);																					#kW/K
param alpha_h{h in House}	:= (1/Mcp_0h[h])/(exp(UAh_0[h]/Mcp_0h[h])-1);														#K/kW
param alpha_c{h in House}	:= (1/Mcp_0c[h])/(exp(UAc_0[h]/Mcp_0c[h])-1);														#K/kW

#-Standard requirements
param Qh{h in House,p in Period,t in Time[p]} 			:= if U_h[h]*ERA[h]*(T_comfort_min_0[h]-T_ext[p,t])-(HeatGains[h,p,t]+SolarGains[h,p,t])>0 and U_h[h]>0 then U_h[h]*ERA[h]*(T_comfort_min_0[h]-T_ext[p,t])-(HeatGains[h,p,t]+SolarGains[h,p,t]) else 0;
param Th_return{h in House,p in Period,t in Time[p]} 	:= if U_h[h]>0 then T_comfort_min_0[h] + Qh[h,p,t]*alpha_h[h] else T_comfort_min_0[h];
param Th_supply{h in House,p in Period,t in Time[p]} 	:= if U_h[h]>0 then Qh[h,p,t]/Mcp_0h[h] + Th_return[h,p,t] else T_comfort_min_0[h];
param Qc{h in House,p in Period,t in Time[p]} 			:= if U_h[h]*ERA[h]*(T_comfort_min_0[h]-T_ext[p,t])-(HeatGains[h,p,t]+SolarGains[h,p,t])<0 and Cooling[h] > 0 then -U_h[h]*ERA[h]*(T_comfort_min_0[h]-T_ext[p,t])+(HeatGains[h,p,t]+SolarGains[h,p,t]) else 0;
param Tc_return{h in House,p in Period,t in Time[p]} 	:= T_comfort_min_0[h] - Qc[h,p,t]*alpha_c[h];
param Tc_supply{h in House,p in Period,t in Time[p]} 	:= -Qc[h,p,t]/Mcp_0c[h] + Tc_return[h,p,t];

#-Non-standard requirements																					
param House_Q_heating_max_d{h in House,p in Period,t in Time[p]} := Qh[h,p,t]+0.25*Qh_0[h]+epsilon;
param House_Q_cooling_max_d{h in House,p in Period,t in Time[p]} := Qc[h,p,t]+0.25*Qc_0[h]+epsilon;

#-heating
subject to House_streams_heating_c1{h in House,p in Period,t in Time[p]}:
sum{se in Services,st in StreamsOfService[se] inter StreamsOfBuilding[h]:se='SH' and Streams_Hin[st]=0}(Streams_Mcp[st,p,t]*HC_Streams_Mult[se,st,p,t]) <= Mcp_0h[h];

subject to House_streams_heating_c2{h in House,p in Period,t in Time[p]}:
sum{se in Services,st in StreamsOfService[se] inter StreamsOfBuilding[h]:se='SH' and Streams_Hin[st]=0}(Streams_Q[se,st,p,t]) = House_Q_heating[h,p,t];

#-cooling 
subject to House_streams_cooling_c1{h in House,p in Period,t in Time[p]}:
sum{se in Services,st in StreamsOfService[se] inter StreamsOfBuilding[h]:se='Cooling' and Streams_Hout[st]=0}(Streams_Mcp[st,p,t]*HC_Streams_Mult[se,st,p,t]) <= Mcp_0c[h];

subject to House_streams_cooling_c2{h in House,p in Period,t in Time[p]}:
sum{se in Services,st in StreamsOfService[se] inter StreamsOfBuilding[h]:se='Cooling' and Streams_Hout[st]=0}(Streams_Q[se,st,p,t]) = House_Q_cooling[h,p,t];

#-Standard energy balance
subject to House_energy_balance{h in House,p in Period,t in Time[p] diff {last(Time[p])}}:
(ERA[h]*HeatCapacity[h]/1000)*(T_in[h,p,next(t,Time[p])] - T_in[h,p,t])/dt[p] = (U_h[h]*ERA[h])*(T_ext[p,t]-T_in[h,p,t]) +
																					(House_Q_heating[h,p,t]-House_Q_cooling[h,p,t]) + HeatGains[h,p,t] + SolarGains[h,p,t];

subject to House_EB_cyclic1{h in House,p in Period,t in Time[p]:t=last(Time[p])}:
(ERA[h]*HeatCapacity[h]/1000)*(T_in[h,p,first(Time[p])] - T_in[h,p,t])/dt[p] = (U_h[h]*ERA[h])*(T_ext[p,t]-T_in[h,p,t]) +
																					(House_Q_heating[h,p,t]-House_Q_cooling[h,p,t]) + HeatGains[h,p,t] + SolarGains[h,p,t];

#-additional constraints
subject to no_ElectricalHeater_without_HP{h in House}:
2 * sum{uj in UnitsOfType['HeatPump'] inter UnitsOfHouse[h]} Units_Use[uj] >= sum{ui in UnitsOfType['ElectricalHeater'] inter UnitsOfHouse[h]} Units_Use[ui];

subject to no_NG_boiler_with_HP{h in House}:
sum{uj in UnitsOfType['HeatPump'] inter UnitsOfHouse[h]} (Units_Use[uj]) + sum{ui in UnitsOfType['NG_Boiler'] inter UnitsOfHouse[h]} (Units_Use[ui]) <= 1;

######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# GRID
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

#--------------------------------------------------------------------------------------------------------------------#
# Grid connection costs
#--------------------------------------------------------------------------------------------------------------------#
param Cost_connection{l in ResourceBalances} default 0; # CHF/kW/month

var peak_exchange_House{l in ResourceBalances, h in HousesOfLayer[l]} >= 0;
var Costs_grid_connection_House{l in ResourceBalances, h in HousesOfLayer[l]} >= 0;
var Costs_grid_connection >= 0;

subject to peak_exchange_calculation{l in ResourceBalances, h in HousesOfLayer[l], p in PeriodStandard,t in Time[p]}:
peak_exchange_House[l,h] >= (Grid_supply[l,h,p,t]+Grid_demand[l,h,p,t]);

subject to grid_connection_House{l in ResourceBalances, h in HousesOfLayer[l]}:
Costs_grid_connection_House[l,h] = 12*Cost_connection[l]*peak_exchange_House[l,h];

subject to grid_connection_total:
Costs_grid_connection = sum{l in ResourceBalances, h in HousesOfLayer[l]} Costs_grid_connection_House[l,h];

#--------------------------------------------------------------------------------------------------------------------#
# Grid capacity constraints
#--------------------------------------------------------------------------------------------------------------------#

subject to LineCapacity_supply{l in ResourceBalances,hl in HousesOfLayer[l],p in Period,t in Time[p]}:
Grid_supply[l,hl,p,t] <= LineCapacity[l,hl];

subject to LineCapacity_demand{l in ResourceBalances,hl in HousesOfLayer[l],p in Period,t in Time[p]}:
Grid_demand[l,hl,p,t] <= LineCapacity[l,hl];

#--------------------------------------------------------------------------------------------------------------------#
# Transformer capacity constraints
#--------------------------------------------------------------------------------------------------------------------#

subject to Network_capacity_supply{l in ResourceBalances,p in PeriodStandard,t in Time[p]}:
Network_supply[l,p,t] <= Network_capacity[l];

subject to Network_capacity_demand{l in ResourceBalances,p in PeriodStandard,t in Time[p]}:
Network_demand[l,p,t] <= Network_capacity[l];

#--------------------------------------------------------------------------------------------------------------------#
# No exchanges between buildings
#--------------------------------------------------------------------------------------------------------------------#
subject to disallow_exchanges_1{l in ResourceBalances,p in PeriodStandard,t in Time[p]: l = 'Electricity'}:
sum{h in House} (Grid_supply[l,h,p,t]) = Network_supply[l,p,t];

subject to disallow_exchanges_2{l in ResourceBalances,p in PeriodStandard,t in Time[p]: l = 'Electricity'}:
sum{h in House} (Grid_demand[l,h,p,t]) = Network_demand[l,p,t];
