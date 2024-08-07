#####################################################################################################################
#--------------------------------------------------------------------------------------------------------------------#
# Methane storage tank
#--------------------------------------------------------------------------------------------------------------------#
######################################################################################################################

# Storage tank without any compression step considered

var CH4_E_stored{h in House,u in UnitsOfType['CH4storage'], hy in Year} >= 0;

subject to CH4_EB_c2{h in House,u in UnitsOfType['CH4storage'], hy in Year}:
(CH4_E_stored[h,u,next(hy,Year)]-CH4_E_stored[h,u,hy]) = 
	(Units_demand['Biogas',u,PeriodOfYear[hy],TimeOfYear[hy]] - Units_supply['Biogas',u,PeriodOfYear[hy],TimeOfYear[hy]])*dt[PeriodOfYear[hy]];

#--SoC constraints
subject to CH4_c1{h in House,u in UnitsOfType['CH4storage'], hy in Year}:
CH4_E_stored[h,u,hy] <= Units_Mult[u];
