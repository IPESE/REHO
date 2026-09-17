######################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
#---ACTORS: MOBILITY COSTS OF THE RENTERS
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################
# Read after actors_problem.mod when the district includes electric vehicles (EV_district): the parameters of the
# mobility sector are declared by mobility.mod and evehicle.mod, which are then read too.

subject to Costs_opex_renter0{h in House}:
C_op_renters_mobility[h] = Cost_travel * sum{d in Distances} DailyDist[d] / EV_eff_travel / EV_eff_ch / ff_EV["EV_district"] * Population * 365 * ERA[h] / sum{i in House}(ERA[i]) * sum{t in Distances} (max_share_modes["cars", t]-max_share_modes["PT", t]-max_share_modes["MD", t]);
