"""Thermal envelope renovation: post-renovation U-values, costs and embodied emissions."""

from reho.logger import get_logger
from reho.model.preprocessing.QBuildings import get_Uh_corrected

logger = get_logger(__name__)

#: Elements of the thermal envelope that can be renovated independently.
RENOVATION_ELEMENTS = ["facade", "footprint", "roof", "window"]

#: Construction period of QBuildings -> period used by ``renovation.csv``.
CONSTRUCTION_PERIOD_TO_RENOVATION_PERIOD = {
    '<1919': "<1918", '1919-1945': "1919-1948", '1946-1960': "1949-1978", '1961-1970': "1949-1978",
    '1971-1980': "1949-1978", '1981-1990': "1979-1994", '1991-2000': "1995-2001", '2001-2005': "2002-2006",
    '2006-2010': '>2006', '>2010': ">2006",
}

#: Multiplier applied to the reference renovation costs of ``renovation.csv``.
RENOVATION_COST_FACTOR = 1.16

#: Share of the facade made of windows, by default and for residential buildings.
DEFAULT_GLASS_RATIO = 0.5
RESIDENTIAL_GLASS_RATIO = 0.3

#: SIA affectation classes considered residential, hence less glazed.
RESIDENTIAL_SIA_CLASSES = ("I", "II")

#: Ratio between the heated floor area of a storey and the building footprint,
#: accounting for the walls' own footprint.
FLOOR_AREA_TO_FOOTPRINT = 0.93

#: Below this improvement in U_h, a renovation package is considered to change nothing
#: and is charged nothing [kW/m2/K].
NEGLIGIBLE_UH_IMPROVEMENT = 1e-6

#: Minimum improvement imposed on the overall heat-loss coefficient [kW/m2/K].
#: A renovation package must reduce U_h, if only marginally: without this floor the
#: master problem can pay for a package that does not improve the envelope at all.
MIN_UH_IMPROVEMENT = 1e-5


def U_h_renovation(buildings_data, df_U_values):
    """Overall heat-loss coefficient of a building after renovation.

    Parameters
    ----------
    buildings_data : dict
        Characteristics of one building, including its current ``U_h``.
    df_U_values : pandas.DataFrame
        Post-renovation U-value of each envelope element, per construction period.

    Returns
    -------
    float
        The renovated ``U_h`` [kW/m2/K], always at least
        :data:`MIN_UH_IMPROVEMENT` below the current value.
    """
    U_h_data = buildings_data['U_h']
    buildings_data = {"dummy": buildings_data}
    buildings_data = get_Uh_corrected(buildings_data, df_U_values)
    U_h_ins_data = buildings_data["dummy"]["U_h"]

    if U_h_ins_data + MIN_UH_IMPROVEMENT >= U_h_data:
        # A building may already be better insulated than the reference values of its
        # construction period, e.g. after an earlier renovation: without this floor, the
        # model could buy a renovation that degrades its envelope.
        logger.debug(
            "Renovation does not improve U_h (%.5f -> %.5f); capping it at a %.0e improvement.",
            U_h_data, U_h_ins_data, MIN_UH_IMPROVEMENT,
        )
        U_h_ins_data = U_h_data - MIN_UH_IMPROVEMENT
    return U_h_ins_data


def select_renovation_option(local_data, renovation_option):
    """Build the U-values and the cost table of one renovation package.

    Parameters
    ----------
    local_data : dict
        Location data, holding ``df_renovation_targets`` and ``df_renovation``.
    renovation_option : str
        Slash-separated elements to renovate, e.g. ``'window/facade/roof'``.

    Returns
    -------
    df_Uh : pandas.DataFrame
        U-value of every envelope element per construction period, with the
        renovated elements replaced by their post-renovation value.
    df_costs : pandas.DataFrame
        Cost and embodied emissions per element, zeroed for elements left untouched.

    Raises
    ------
    ValueError
        If the package names an element that is not part of the envelope.
    """
    options = renovation_option.split("/")
    unknown = [element for element in options if element not in RENOVATION_ELEMENTS]
    if unknown:
        raise ValueError(
            f"Unknown renovation element(s) {unknown} in {renovation_option!r}. "
            f"Expected a '/'-separated subset of {RENOVATION_ELEMENTS}."
        )

    df_U_values = local_data["df_renovation_targets"].copy()
    columns = ["U_required_" + item if item in options else "U_" + item for item in RENOVATION_ELEMENTS]
    df_Uh = df_U_values[columns].copy()
    df_Uh.columns = df_Uh.columns.str.replace(r'^U_required', 'U', regex=True)

    df_costs = local_data["df_renovation"].copy()
    for element in RENOVATION_ELEMENTS:
        if element not in options:
            df_costs.loc[df_costs.index.get_level_values('element') == element, :] = 0

    return df_Uh, df_costs


def renovation_cost_co2(buildings_data, local_data, renovation_option):
    """Post-renovation U-value, investment cost and embodied emissions of one building.

    A building may mix construction periods (``period``/``ratio`` are
    slash-separated); the impacts are then the ratio-weighted sum over those periods.

    Parameters
    ----------
    buildings_data : dict
        Characteristics of one building: ``U_h``, ``period``, ``ratio``, ``id_class``,
        ``area_facade_m2``, ``SolarRoofArea``, ``ERA``, ``count_floor``, and
        optionally ``glass_ratio``.
    local_data : dict
        Location data, holding ``df_renovation_targets`` and ``df_renovation``.
    renovation_option : str
        Slash-separated elements to renovate, e.g. ``'window/facade/roof/footprint'``.

    Returns
    -------
    Uh_ins : float
        Heat-loss coefficient after renovation [kW/m2/K].
    cost : float
        Investment cost of the package [CHF].
    gwp : float
        Embodied emissions of the package [kgCO2eq].
    """
    Uh = buildings_data["U_h"]
    df_U_values, df_costs = select_renovation_option(local_data, renovation_option)
    Uh_ins = U_h_renovation(buildings_data.copy(), df_U_values)

    if Uh - Uh_ins < NEGLIGIBLE_UH_IMPROVEMENT:
        # The package does not measurably improve the envelope: charge nothing for it.
        return Uh_ins, 0.0, 0.0

    df_costs.columns = ["cost", "gwp"]
    periods, ratios, id_classes = _building_periods(buildings_data)

    impacts = {}
    for impact in df_costs:
        impacts[impact] = 0.0
        for period, ratio, id_class in zip(periods, ratios, id_classes):
            glass = _glass_ratio(buildings_data, id_class)
            unit_cost = df_costs[impact].xs(CONSTRUCTION_PERIOD_TO_RENOVATION_PERIOD[period])
            facade_area = buildings_data["area_facade_m2"]
            footprint_area = buildings_data["ERA"] / buildings_data["count_floor"] / FLOOR_AREA_TO_FOOTPRINT
            impacts[impact] += ratio * (
                facade_area * ((1 - glass) * unit_cost["facade"] + glass * unit_cost["window"])
                + buildings_data["SolarRoofArea"] * unit_cost["roof"]
                + footprint_area * unit_cost["footprint"]
            )

    return Uh_ins, impacts["cost"] * RENOVATION_COST_FACTOR, impacts["gwp"]


def _building_periods(buildings_data):
    """Construction periods, area ratios and SIA classes of a building, aligned.

    QBuildings describes a building that spans several construction periods with
    slash-separated lists; they are not guaranteed to have the same length.

    Returns
    -------
    periods, ratios, id_classes : list
        Three lists of equal length.
    """
    periods = buildings_data["period"].split("/")
    ratios = [float(x) for x in buildings_data["ratio"].split("/")]
    id_classes = buildings_data["id_class"].split("/")

    if len(periods) < len(ratios):
        periods = periods + [periods[0]] * (len(ratios) - len(periods))
    if len(periods) > len(ratios):
        ratios = ratios + [0.0] * (len(periods) - len(ratios))
    if len(id_classes) < len(periods):
        id_classes = id_classes + [id_classes[0]] * (len(periods) - len(id_classes))

    return periods, ratios, id_classes


def _glass_ratio(buildings_data, id_class):
    """Share of the facade area occupied by windows.

    Taken from ``buildings_data['glass_ratio']`` when the caller provides one, and
    otherwise deduced from the SIA affectation class: residential buildings have
    noticeably less glazing than service or commercial ones.
    """
    if "glass_ratio" in buildings_data:
        return buildings_data["glass_ratio"]
    return RESIDENTIAL_GLASS_RATIO if id_class in RESIDENTIAL_SIA_CLASSES else DEFAULT_GLASS_RATIO
