#-Variable list 
# BAT_E_stored														#-Vars Battery

#-Constraints list
# BAT_EB_c1,BAT_c1,BAT_c2,BAT_c3,BAT_c4,BAT_EB_cyclic1				#-Csts Battery



#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---BATTERY MODEL
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
#-First-order electrical storage model including:
#	1. dis-/charging efficiencies 
#	2. self-discharging efficiency 
#	3. dis-/charging limits
#-References : 
# [1]	F. Oldewurtel et al., Building Control and Storage Management with [...], 2010 
# [2]   M. Koller et al., Defining a Degradation Cost Function for Optimal [...], 2013
# ----------------------------------------- PARAMETERS ---------------------------------------
param BAT_eff_ch{u in UnitsOfType['Battery']} 	default 0.9;			#-	[1]
param BAT_eff_di{u in UnitsOfType['Battery']} 	default 0.9;			#-	[1]
param BAT_limit_ch{u in UnitsOfType['Battery']} default 0.8;			#-	[2]
param BAT_limit_di{u in UnitsOfType['Battery']} default 0.2;			#-	[1]
param BAT_efficiency{u in UnitsOfType['Battery']} default 0.99992;		#-	[1]

# ----------------------------------------- VARIABLES ---------------------------------------
var BAT_E_stored{u in UnitsOfType['Battery'],p in Period,t in Time[p]} >= 0;	#kWh

# ---------------------------------------- CONSTRAINTS ---------------------------------------
#--Energy balance
subject to BAT_EB_c1{u in UnitsOfType['Battery'],p in Period,t in Time[p] diff {last(Time[p])}}:
(BAT_E_stored[u,p,next(t,Time[p])] - BAT_efficiency[u]*BAT_E_stored[u,p,t]) = 
	( BAT_eff_ch[u]*Units_demand['Electricity',u,p,t] - (1/BAT_eff_di[u])*Units_supply['Electricity',u,p,t] )*dt[p];	#kWh

#--SoC constraints
subject to BAT_c1{u in UnitsOfType['Battery'],p in Period,t in Time[p]}:
BAT_E_stored[u,p,t] <= BAT_limit_ch[u]*Units_Mult[u];																	#kWh

subject to BAT_c2{u in UnitsOfType['Battery'] ,p in Period,t in Time[p]}:
BAT_E_stored[u,p,t] >= BAT_limit_di[u]*Units_Mult[u];																	#kWh

subject to BAT_c3{u in UnitsOfType['Battery'] ,p in Period,t in Time[p]}:
Units_demand['Electricity',u,p,t]*dt[p] <= (BAT_limit_ch[u]-BAT_limit_di[u])*Units_Mult[u];							#kW

subject to BAT_c4{u in UnitsOfType['Battery'],p in Period,t in Time[p]}:
Units_supply['Electricity',u,p,t]*dt[p] <= (BAT_limit_ch[u]-BAT_limit_di[u])*Units_Mult[u];							#kW
																										
#--Cyclic
subject to BAT_EB_cyclic1{u in UnitsOfType['Battery'],p in Period}:
(BAT_E_stored[u,p,first(Time[p])] - BAT_efficiency[u]*BAT_E_stored[u,p,last(Time[p])]) =
	(BAT_eff_ch[u]*Units_demand['Electricity',u,p,last(Time[p])] - (1/BAT_eff_di[u])*Units_supply['Electricity',u,p,last(Time[p])])*dt[p];	#kWh


#-----------------------------------------------------------------------------------------------------------------------	
