
######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#--- Heat curtailment unit
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
# This unit allows to disregard heat from storage technologies without limitation or cost. 
# Constraint c2 ensure the maximal disregarded heat corresponds to storage production.
# -------------------------------------------- PARAMETERS ------------------------------------------
	
# ----------------------------------------- VARIABLES ---------------------------------------
var Curtailed_heat{h in House,u in UnitsOfType['HeatCurtailment'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]}	>= 0,<= 1e7;	#kg/h

#-STREAMS
#-cold stream from T-1 to T -> heat (mass) incoming to the slice T, here from point of view of T
subject to Curtailed_heat_c1{h in House,u in UnitsOfType['HeatCurtailment'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]}:
Curtailed_heat[h,u,st,p,t] = (sum{sq in ServicesOfStream[st]} Streams_Q[sq,st,p,t])*dt[p];		#kW

subject to Curtailed_heat_c2{h in House,u in UnitsOfType['HeatCurtailment'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]}:
Curtailed_heat[h,u,st,p,t] <= sum{us in UnitsOfStorage inter UnitsOfHouse[h],sts in StreamsOfUnit[us], sq in ServicesOfStream[sts]} Streams_Q[sq,sts,p,t] ;		#kW

subject to Curtailed_heat_c3{h in House,u in UnitsOfType['HeatCurtailment'] inter UnitsOfHouse[h],st in StreamsOfUnit[u],p in Period,t in Time[p]}:
Curtailed_heat[h,u,st,p,t] <= Units_Mult[u];		#kW

#-----------------------------------------------------------------------------------------------------------------------
#TEST 
# subject to Curtailed_heat_c4{h in House,u in UnitsOfType['HeatCurtailment'] inter UnitsOfHouse[h]}:
# sum{st in StreamsOfUnit[u],p in Period, t in Time[p]}(Curtailed_heat[h,u,st,p,t]) >= 20 ;#kWh
