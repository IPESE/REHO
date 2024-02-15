import urllib3
from reho.model.preprocessing.QBuildings import *
import time
from datetime import date, datetime
from typing import Dict, Optional, Union
import requests as rq
from shapely import wkt
import json

FIND_PATTERN = "PREFIX\\s*(.*?)\n"
SPLIT_PATTERN = ":\\s*"

DATA_TYPES_TO_PYTHON_CLS = {
    "http://www.w3.org/2001/XMLSchema#integer": int,
    "http://www.w3.org/2001/XMLSchema#float": float,
    "http://www.w3.org/2001/XMLSchema#double": float,
    "http://www.w3.org/2001/XMLSchema#decimal": float,
    "http://www.w3.org/2001/XMLSchema#date": date.fromisoformat,
    "http://www.w3.org/2001/XMLSchema#dateTime": (
        lambda x: datetime.strptime(x.rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
    ),
    "http://www.opengis.net/ont/geosparql#wktLiteral": wkt.loads,
    "http://www.openlinksw.com/schemas/virtrdf#Geometry": wkt.loads,
    "https://www.w3.org/2001/XMLSchema#integer": int,
    "https://www.w3.org/2001/XMLSchema#float": float,
    "https://www.w3.org/2001/XMLSchema#double": float,
    "https://www.w3.org/2001/XMLSchema#decimal": float,
    "https://www.w3.org/2001/XMLSchema#date": date.fromisoformat,
    "https://www.w3.org/2001/XMLSchema#dateTime": (
        lambda x: datetime.strptime(x.rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
    ),
    "https://www.opengis.net/ont/geosparql#wktLiteral": wkt.loads,
    "https://www.openlinksw.com/schemas/virtrdf#Geometry": wkt.loads,
}

GEODATA_TYPES = set(
    [
        "http://www.opengis.net/ont/geosparql#wktLiteral",
        "http://www.openlinksw.com/schemas/virtrdf#Geometry",
        "https://www.opengis.net/ont/geosparql#wktLiteral",
        "https://www.openlinksw.com/schemas/virtrdf#Geometry",
    ]
)


def requests_retry_session(
        retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None
):
    session = session or rq.Session()
    retry = urllib3.util.Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = rq.adapters.HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


class SparqlClient:
    def __init__(
            self,
            base_url: str = None,
            timeout: Optional[int] = 15,
            output: Optional[str] = "pandas",
            user: Optional[str] = None,
            password: Optional[str] = None,
    ) -> None:

        self.BASE_URL = base_url
        self.last_request = 0
        self.HEADERS = {
            "Accept": "application/sparql-results+json",
        }
        self.prefixes = dict()
        self.timeout = timeout
        self.output = output

        self.session = requests_retry_session()
        if user and password:
            self.session.auth = (user, password)

    def _normalize_prefixes(self, prefixes: Dict) -> str:
        """Transfrom prefixes map to SPARQL-readable format
        Args:
            prefixes: 		prefixes to be normalized

        Returns
            str             SPARQL-readable prefix definition
        """

        normalized_prefixes = "\n".join(
            "PREFIX %s" % ": ".join(map(str, x)) for x in prefixes.items()
        )
        if normalized_prefixes:
            normalized_prefixes += "\n"
        return normalized_prefixes

    def add_prefixes(self, prefixes: Dict) -> None:
        """Define prefixes to be added to every query
        Args:
            prefixes: 		prefixes to be added to every query

        Returns
            None
        """

        self.prefixes = {**self.prefixes, **prefixes}

    def remove_prefixes(self, prefixes: Dict) -> None:
        """Remove prefixes from the prefixes are added to every query
        Args:
            prefixes: 		prefixes to be removed from self.prefixes

        Returns
            None
        """

        for prefix in prefixes:
            self.prefixes.pop(prefix, None)

    def _format_query(self, query: str) -> str:
        """Format SPARQL query to include in-memory prefixes.
        Prefixes already defined in the query have precedence, and are not overwritten.
            Args:
                query: 				user-defined SPARQL query

            Returns
                str:	            SPARQL query with predefined prefixes
        """

        prefixes_in_query = dict(
            [
                re.split(SPLIT_PATTERN, prefix, 1)
                for prefix in re.findall(FIND_PATTERN, query)
            ]
        )
        prefixes_to_add = {
            k: v for (k, v) in self.prefixes.items() if k not in prefixes_in_query
        }

        return self._normalize_prefixes(prefixes_to_add) + query

    def send_query(self, query: str, timeout: Optional[int] = 0) -> pd.DataFrame:
        """Send SPARQL query. Transform results to pd.DataFrame.
        Args:
            query: 				full SPARQL query
            timeout:            timeout (in seconds) for this query. If not defined, the self.timeout will be used.

        Returns
            pd.DataFrame	    query results
        """

        request = {"query": self._format_query(query)}

        if time.time() < self.last_request + 1:
            time.sleep(1)
        self.last_request = time.time()

        if timeout == 0:
            timeout = self.timeout

        if timeout is not None:
            response = self.session.get(
                self.BASE_URL, headers=self.HEADERS, params=request, timeout=timeout
            )
        else:
            response = self.session.get(
                self.BASE_URL, headers=self.HEADERS, params=request
            )
        response.raise_for_status()
        response = response.json()

        if "head" not in response:
            raise ExecutionError(
                "{}\n Triplestore error code: {}".format(
                    response["message"], response["code"]
                )
            )

        if not response["results"]["bindings"]:
            raise NotFoundError()

        if self.output == "pandas":
            return self._normalize_results(response)
        elif self.output == "dict":
            return response
        else:
            raise TypeError(
                "Invalid output type. Choose `pandas` or `dict` as output type"
            )

    def _normalize_results(
            self, response: Dict
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        """Normalize response from SPARQL endpoint. Transform json structure to table. Convert observations to python data types.
        Args:
            response: 			raw response from SPARQL endpoint

        Returns
            pd.DataFrame	    response from SPARQL endpoint in a tabular form, with python data types
        """

        cols = response["head"]["vars"]
        data = dict(zip(cols, [[] for i in range(len(cols))]))

        has_geo_data = False
        for row in response["results"]["bindings"]:
            for key in cols:

                if key in row:

                    value = row[key]["value"]
                    if "datatype" in row[key]:
                        datatype = row[key]["datatype"]
                        value = DATA_TYPES_TO_PYTHON_CLS[datatype](value)

                        if datatype in GEODATA_TYPES:
                            has_geo_data = True
                            geometry_col = key

                else:
                    value = None

                data[key].append(value)

        if has_geo_data:
            return gpd.GeoDataFrame.from_dict(data).set_geometry(col=geometry_col)
        else:
            return pd.DataFrame.from_dict(data)


class GraphlyError(Exception):
    pass


class NotFoundError(GraphlyError):
    pass


class ExecutionError(GraphlyError):
    pass


cantons = {'id': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26],
           'name_fr': ['Zurich', 'Berne', 'Lucerne', 'Uri', 'Schwytz', 'Obwald', 'Nidwald', 'Glaris', 'Zoug',
                       'Fribourg',
                       'Soleure', 'Bâle-ville', 'Bâle-campagne', 'Schaffhouse',
                       'Appenzell Rhodes-Extérieures', 'Appenzell Rhodes-Intérieures', 'St-Gall', 'Grisons', 'Argovie',
                       'Thurgovie', 'Tessin', 'Vaud', 'Valais', 'Neuchâtel', 'Genève', 'Jura'],
           'name_de': ["Zürich", 'Bern', 'Luzern', 'Uri', "Schwyz", "Obwalden", "Nidwalden", "Glarus", "Zug",
                       'Freiburg',
                       "Solothurn", "Basel-Stadt", 'Basel-Landschaft', "Schaffhausen",
                       'Appenzell Ausserrhoden', 'Appenzell Innerrhoden', 'St. Gallen', "Graubünden", "Aargau",
                       'Thurgau', 'Tessin', 'Waadt', 'Wallis', 'Neuenburg', 'Genf', 'Jura'],
           'name_en': ["Zurich", 'Bern', 'Lucerne', 'Uri', "Schwyz", "Obwalden", "Nidwalden", "Glarus", "Zug",
                       'Freiburg',
                       "Solothurn", "Basel-City", 'Basel-Country', "Schaffhausen",
                       'Appenzell Outer-Rhodes', 'Appenzell Inner-Rhodes', 'St. Gallen', "Graubünden", "Aargau",
                       'Thurgau', 'Tessin', 'Vaud', 'Valais', 'Neuchâtel', 'Geneva', 'Jura']}
cantons = pd.DataFrame.from_dict(cantons).set_index('id')

sparql = SparqlClient("https://lindas.admin.ch/query")
geosparql = SparqlClient("https://ld.geo.admin.ch/query")

sparql.add_prefixes({
    "schema": "<http://schema.org/>",
    "cube": "<https://cube.link/>",
    "elcom": "<https://energy.ld.admin.ch/elcom/electricityprice/dimension/>",
    "admin": "<https://schema.ld.admin.ch/>",
})

geosparql.add_prefixes({
    "dct": "<http://purl.org/dc/terms/>",
    "geonames": "<http://www.geonames.org/ontology#>",
    "schema": "<http://schema.org/>",
    "geosparql": "<http://www.opengis.net/ont/geosparql#>",
})


def get_providers_by_municipality_id(city=None, from_csv=True):
    """
    Gives the electricity providers for a given municipality.

    Parameters
    ----------
    city : (int, str, QBuildingsReader)
        The city from which the providers should be retrieved. It can be in the form of its ID, its name or retrieved by
        the QBuildingsReader
        If None is passed, the whole correspondance table between the municipalities and the providers is returned.
    from_csv : bool
        A correspondance table has been saved as a csv to avoid querying the ELCOM database. However, if you want to
        be sure that it is the last municipality IDs or if you know some providers have changed since the date of the
        corresponding table, set it to False.

    Returns
    -------
    pd.DataFrame which columns are ['id_city', 'commune', 'id_operator', 'operator'] for the given city.
    Notes
    -----
    - The correspondance table is dated from 01.02.2024
    - ``QBuildingsReader`` object can be passed to 'city' for automatic localization, from the initial building selection.

    Examples
    --------
    >>> get_providers_by_municipality_id(city='Rüderswil')
    """
    city_link = 'https://ld.admin.ch/municipality/'
    op_link = 'https://energy.ld.admin.ch/elcom/electricityprice/operator/'

    if isinstance(city, QBuildingsReader):
        city = city.data['transformers']['id_city'][0]
        city_query = '<' + city_link + str(city) + '>'
    elif isinstance(city, int):
        city_query = '<' + city_link + str(city) + '>'
    else:
        city_query = "?id_city"

    #  Use csv of correspondance from 01.02.2024
    if from_csv:
        communes = pd.read_csv(os.path.join(path_to_electricity, 'correspondance_table_municipality_operator.csv'),
                               index_col=0)
        if city is not None:
            mask = (communes['id_city'] == city) + (communes['commune'] == city)
            communes = communes.loc[mask]
            if communes.empty:
                print('No corresponding city to the given identifier')

    else:
        query = """
            SELECT DISTINCT ?id_city ?commune ?id_operator ?operator WHERE {
                <https://energy.ld.admin.ch/elcom/electricityprice> <https://cube.link/observationSet> ?observationSet0 .
                ?observationSet0 <https://cube.link/observation> ?source0 .
            ?source0 <https://energy.ld.admin.ch/elcom/electricityprice/dimension/municipality> city_to_replace .
            ?source0 <https://energy.ld.admin.ch/elcom/electricityprice/dimension/operator> ?id_operator .
            
            OPTIONAL {
                city_to_replace <http://schema.org/name> ?commune_0 .
                FILTER (
                  LANGMATCHES(LANG(?commune_0), "fr")
                )
              }
              OPTIONAL {
                city_to_replace <http://schema.org/name> ?commune_1 .
                FILTER (
                  LANGMATCHES(LANG(?commune_1), "de")
                )
              }
              OPTIONAL {
                city_to_replace <http://schema.org/name> ?commune_2 .
                FILTER (
                  LANGMATCHES(LANG(?commune_2), "it")
                )
              }
              OPTIONAL {
                city_to_replace <http://schema.org/name> ?commune_3 .
                FILTER (
                  LANGMATCHES(LANG(?commune_3), "en")
                )
              }
              OPTIONAL {
                city_to_replace <http://schema.org/name> ?commune_4 .
                FILTER (
                  (LANG(?commune_4) = "")
                )
              }
            BIND(COALESCE(?commune_0, ?commune_1, ?commune_2, ?commune_3, ?commune_4) AS ?commune)    
            
            OPTIONAL {
                ?id_operator <http://schema.org/name> ?operator_0 .
                FILTER (
                  LANGMATCHES(LANG(?operator_0), "fr")
                )
              }
              OPTIONAL {
                ?id_operator <http://schema.org/name> ?operator_1 .
                FILTER (
                  LANGMATCHES(LANG(?operator_1), "de")
                )
              }
              OPTIONAL {
                ?id_operator <http://schema.org/name> ?operator_2 .
                FILTER (
                  LANGMATCHES(LANG(?operator_2), "it")
                )
              }
              OPTIONAL {
                ?id_operator <http://schema.org/name> ?operator_3 .
                FILTER (
                  LANGMATCHES(LANG(?operator_3), "en")
                )
              }
              OPTIONAL {
                ?id_operator <http://schema.org/name> ?operator_4 .
                FILTER (
                  (LANG(?operator_4) = "")
                )
              }
              BIND(COALESCE(?operator_0, ?operator_1, ?operator_2, ?operator_3, ?operator_4) AS ?operator)
            }
            """
        query = query.replace('city_to_replace', city_query)
        communes = sparql.send_query(query)
        if communes.loc[0, 'id_city'] is None:
            communes['id_city'] = int(city)
        else:
            communes['id_city'] = communes['id_city'].apply(lambda row: int(row.split(city_link)[1]))
        communes['id_operator'] = communes['id_operator'].apply(lambda row: int(row.split(op_link)[1]))

    return communes


def get_prices_from_elcom_by_canton(year=2024, canton=None, category=None, tva=None, export_path=None):
    """
    Queries the electricity retail prices from the ELCOM database.
    Year, canton and consumer category can be specified.
    TVA is applied by default or can be adapted as a scaling factor.

    Parameters
    ----------
    year : int
        Year from which the electricity prices must be retrieved.
    canton : str/int
        Canton from which the electricity prices must be retrieved. Can be in form of canton ID or canton name.
    category : str
        Category from which the electricity prices must be retrieved.
    tva : bool
        Whether the tva should be included in the final results or not.
    export_path : str
        If given, export the prices with the parameter required at the path.

    Returns
    -------
    pd.DataFrame with the electricity price and its components.

    See also
    --------
    get_prices_from_elcom_by_city : To retrieve the ELCOM prices by city.
    get_injection_prices : To obtain the injection prices instead.

    Notes
    -----
    - A ``QBuildingsReader`` object can be passed to 'canton' for automatic localization.
    - List and description of the available categories are available at the `ELCOM website <https://www.prix-electricite.elcom.admin.ch/>`_.
    - The TVA on electricity changed in 2024, from 7.7% to 8.1%.

    Examples
    --------
    >>> prices = electricity_prices.get_prices_from_elcom_by_canton(canton='Geneva', category='H4')
    >>> prices
        Year  Canton Category  ...  community_fees  aidfee  finalcosts
    0  2024  Geneva       H4  ...         1.42824     2.3   30.925972
    [1 rows x 9 columns]
    """

    canton_link = 'https://ld.admin.ch/canton/'
    cat_link = 'https://energy.ld.admin.ch/elcom/electricityprice/category/'

    if isinstance(canton, QBuildingsReader):
        canton = canton.data['transformers']['id_canton'][0]
        canton_query = '<' + canton_link + str(canton) + '>'
        bonus_columns = ""
    elif isinstance(canton, str):
        mask = (cantons['name_fr'] == canton) + (cantons['name_de'] == canton) + (cantons['name_en'] == canton)
        canton = str(cantons[mask].first_valid_index())
        canton_query = '<' + canton_link + str(canton) + '>'
        bonus_columns = ""
    elif isinstance(canton, int):
        canton_query = '<' + canton_link + str(canton) + '>'
        bonus_columns = ""
    else:
        canton_query = "?Canton"
        bonus_columns = "?Canton"
    valid_cat = ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7']
    if category in valid_cat:
        cat_query = '<' + cat_link + category + '>'
    elif category is None:
        cat_query = "?Category"
        bonus_columns += "?Category"
    else:
        raise ValueError("The category asked is not a valid one from the elcom.\n"
                         f"Please pick among {valid_cat}.\n")

    query_template = """
    SELECT ?Year ?Canton ?Category ?totalcosts ?energy ?grid ?community_fees ?aidfee
    WHERE {
        <https://energy.ld.admin.ch/elcom/electricityprice-canton> cube:observationSet ?observationSet0 .
        ?observationSet0 cube:observation ?observation .

        ?observation
          elcom:category category_to_replace;
          elcom:canton canton_to_replace;
          elcom:period "year_to_replace"^^<http://www.w3.org/2001/XMLSchema#gYear>;
          elcom:product <https://energy.ld.admin.ch/elcom/electricityprice/product/standard>;
          elcom:total ?totalcosts;
          elcom:gridusage ?grid;
          elcom:energy ?energy;
          elcom:charge ?community_fees;
          elcom:aidfee ?aidfee.
    }
    """

    query = query_template.replace('year_to_replace', str(year))
    query = query.replace('canton_to_replace', canton_query)
    query = query.replace('category_to_replace', str(cat_query))
    query = query.replace('add_columns', str(bonus_columns))
    prices = sparql.send_query(query)
    if prices.loc[0, 'Canton'] is None:
        prices['Canton'] = cantons.loc[int(canton), 'name_en']
    else:
        prices['Canton'] = prices['Canton'].apply(lambda row: cantons.loc[int(row.split(canton_link)[1]), 'name_en'])
    if prices.loc[0, 'Category'] is None:
        prices['Category'] = category
    else:
        prices['Category'] = prices['Category'].apply(lambda row: row.split(cat_link)[1])
    prices['Year'] = year

    # Define custom sorting order
    custom_order = {'H1': 1, 'H2': 2, 'H3': 3, 'H4': 4, 'H5': 5, 'H6': 6, 'H7': 7, 'H8': 8,
                    'C1': 9, 'C2': 10, 'C3': 11, 'C4': 12, 'C5': 13, 'C6': 14, 'C7': 15}
    prices['Category'] = prices['Category'].map(custom_order)

    # Sort the DataFrame based on the "Category" column
    prices = prices.sort_values(by='Category').reset_index(drop=True)

    # Convert back to original category format
    prices['Category'] = prices['Category'].map({v: k for k, v in custom_order.items()})

    if tva is None:
        if year >= 2024:
            tva = 1.081
        else:
            tva = 1.077

    prices['finalcosts'] = tva * prices['totalcosts']

    if isinstance(export_path, str):
        prices.to_csv(os.path.realpath(export_path))

    return prices


def get_prices_from_elcom_by_city(year=2024, city=None, category=None, tva=None, export_path=None):
    """
    Queries the electricity retail prices from the ELCOM database by munipalities.

    Year, municipality and consumer category can be specified.
    TVA is applied by default or can be adapted as a scaling factor.

    Parameters
    ----------
    year : int
        Year from which the electricity prices must be retrieved.
    city : str/int
        Municipality from which the electricity prices must be retrieved. Can be in form of city ID or city name.
        If not given, queries the ELCOM database for the prices in every municipality.
    category : str
        Category from which the electricity prices must be retrieved.
        If not given, prices are given for every consumer category.
    tva : float
        Scaling factor for the resulting prices, initialized as the normal TVA.
    export_path : str
        If given, export the prices with the parameter required at the path.

    Returns
    -------
    pd.DataFrame with the electricity price and its components.

    See also
    --------
    get_prices_from_elcom_by_canton : To retrieve the ELCOM prices by canton.
    get_injection_prices : To obtain the injection prices instead.

    Notes
    -----
    - A ``QBuildingsReader`` object can be passed to 'city' for automatic localization.
    - List and description of the available categories are available at the `ELCOM website <https://www.prix-electricite.elcom.admin.ch/>`_.
    - The TVA on electricity changed in 2024, from 7.7% to 8.1%.

    Examples
    --------
    >>> prices = electricity_prices.get_prices_from_elcom_by_city(city='Geneva', category='H4')
    >>> prices
        Year  City   Category  ...  community_fees  aidfee  finalcosts
    0  2024  Geneva       H4  ...         1.42824     2.3   30.925972
    [1 rows x 9 columns]
    """

    city_link = 'https://ld.admin.ch/municipality/'
    cat_link = 'https://energy.ld.admin.ch/elcom/electricityprice/category/'

    if isinstance(city, QBuildingsReader):
        city = city.data['transformers']['id_city'][0]
        city_query = '<' + city_link + str(city) + '>'
    elif isinstance(city, str):
        cities = pd.read_csv(os.path.join(path_to_electricity, 'correspondance_table_municipality_operator.csv'),
                             index_col=0)
        mask = (cities['id_city'] == city) + (cities['commune'] == city)
        cities = cities[mask]
        if cities.empty:
            print('No corresponding city with that name')
        city = cities.iloc[0]['id_city']
        city_query = '<' + city_link + str(city) + '>'
    elif isinstance(city, int):
        city_query = '<' + city_link + str(city) + '>'
    else:
        city_query = "?id_city"

    valid_cat = ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7']
    if category in valid_cat:
        cat_query = '<' + cat_link + category + '>'
    elif category is None:
        cat_query = "?Category"
    else:
        raise ValueError("The category asked is not a valid one from the elcom.\n"
                         f"Please pick among {valid_cat}.\n")

    query_template = """
    SELECT ?Year ?City ?Provider ?Category ?totalcosts ?energy ?grid ?community_fees ?aidfee
    WHERE {
        <https://energy.ld.admin.ch/elcom/electricityprice> cube:observationSet ?observationSet0 .
        ?observationSet0 cube:observation ?observation .

        ?observation
          elcom:category category_to_replace;
          elcom:municipality city_to_replace;
          elcom:operator ?operator;
          elcom:period "year_to_replace"^^<http://www.w3.org/2001/XMLSchema#gYear>;
          elcom:product <https://energy.ld.admin.ch/elcom/electricityprice/product/standard>;
          elcom:total ?totalcosts;
          elcom:gridusage ?grid;
          elcom:energy ?energy;
          elcom:charge ?community_fees;
          elcom:aidfee ?aidfee.
          
      OPTIONAL {
        city_to_replace <http://schema.org/name> ?commune_0 .
        FILTER (
          LANGMATCHES(LANG(?commune_0), "fr")
        )
      }
      OPTIONAL {
        city_to_replace <http://schema.org/name> ?commune_1 .
        FILTER (
          LANGMATCHES(LANG(?commune_1), "de")
        )
      }
      OPTIONAL {
        city_to_replace <http://schema.org/name> ?commune_2 .
        FILTER (
          LANGMATCHES(LANG(?commune_2), "it")
        )
      }
      OPTIONAL {
        city_to_replace <http://schema.org/name> ?commune_3 .
        FILTER (
          LANGMATCHES(LANG(?commune_3), "en")
        )
      }
      OPTIONAL {
        city_to_replace <http://schema.org/name> ?commune_4 .
        FILTER (
          (LANG(?commune_4) = "")
        )
      }
    BIND(COALESCE(?commune_0, ?commune_1, ?commune_2, ?commune_3, ?commune_4) AS ?City)
          
      OPTIONAL {
        ?operator <http://schema.org/name> ?operator_0 .
        FILTER (
          LANGMATCHES(LANG(?operator_0), "fr")
        )
      }
      OPTIONAL {
        ?operator <http://schema.org/name> ?operator_1 .
        FILTER (
          LANGMATCHES(LANG(?operator_1), "de")
        )
      }
      OPTIONAL {
        ?operator <http://schema.org/name> ?operator_2 .
        FILTER (
          LANGMATCHES(LANG(?operator_2), "it")
        )
      }
      OPTIONAL {
        ?operator <http://schema.org/name> ?operator_3 .
        FILTER (
          LANGMATCHES(LANG(?operator_3), "en")
        )
      }
      OPTIONAL {
        ?operator <http://schema.org/name> ?operator_4 .
        FILTER (
          (LANG(?operator_4) = "")
        )
      }
      BIND(COALESCE(?operator_0, ?operator_1, ?operator_2, ?operator_3, ?operator_4) AS ?Provider)
            
    }
    """

    query = query_template.replace('year_to_replace', str(year))
    query = query.replace('city_to_replace', city_query)
    query = query.replace('category_to_replace', str(cat_query))
    prices = sparql.send_query(query)
    if prices.loc[0, 'Category'] is None:
        prices['Category'] = category
    else:
        prices['Category'] = prices['Category'].apply(lambda row: row.split(cat_link)[1])
    prices['Year'] = year

    # Define custom sorting order
    custom_order = {'H1': 1, 'H2': 2, 'H3': 3, 'H4': 4, 'H5': 5, 'H6': 6, 'H7': 7, 'H8': 8,
                    'C1': 9, 'C2': 10, 'C3': 11, 'C4': 12, 'C5': 13, 'C6': 14, 'C7': 15}
    prices['Category'] = prices['Category'].map(custom_order)

    # Sort the DataFrame based on the "Category" column
    prices = prices.sort_values(by='Category').reset_index(drop=True)

    # Convert back to original category format
    prices['Category'] = prices['Category'].map({v: k for k, v in custom_order.items()})

    if tva is None:
        if year >= 2024:
            tva = 1.081
        else:
            tva = 1.077

    prices['finalcosts'] = tva * prices['totalcosts']

    if isinstance(export_path, str):
        prices.to_csv(os.path.realpath(export_path))

    return prices

def get_vese_key():
    try:
        response = rq.get("https://ipese-lectures.epfl.ch/static/reho.json", timeout=1)
        if response.status_code == 200:
            json_data = response.json()
            api_key_value = json_data.get("API_VESE_KEY")
            return api_key_value
        else:
            return f"Error: {response.status_code}"
    except Exception:
        return False
    
def get_injection_prices(city=None, year=2024, category=None, tva=None):
    """
    Retrieve injection prices from the `pvtarif.ch <https://www.vese.ch/fr/pvtarif/>`_  API.

    The year, municipality and consumer category can be given to query at a more precise level.
    TVA is applied by default or can be adapted as a scaling factor.

    Parameters
    ----------
    city : str or None, optional
        The city for which to retrieve injection prices. If None, prices for all cities will be retrieved.
    year : int, optional
        The year for which to retrieve injection prices. Default is 2024.
    category : str or None, optional
        The energy category for which to retrieve injection prices. If None, prices for the first power category are given.
    tva : float or None, optional
        The Value Added Tax (TVA) multiplier to apply to the total costs. If None, the default TVA value is used.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing injection prices information for each city.

    Raises
    ------
    ExecutionError
        Raised if there is an issue with the HTTP request to the PVTarif API.

    See also
    --------
    get_prices_from_elcom_by_city : To retrieve the ELCOM prices by city.
    get_prices_from_elcom_by_canton : To retrieve the ELCOM prices by canton.

    Notes
    -----
    - The data are not realibly available before 2017.
    - The category corresponds to the one from `ELCOM <https://www.prix-electricite.elcom.admin.ch/>`_.
    - The TVA on electricity changed in 2024, from 7.7% to 8.1%.

    Example
    -------
    >>> retribution_prices = get_injection_prices(year=2023, city='Basel')
    >>> retribution_prices.columns
    Index(['id_city', 'municipality', 'id_operator', 'operator', 'federal_tariff',
       'origin_bonus', 'totalcosts', 'finalcosts'],
      dtype='object')
    >>> retribution_prices
        id_city municipality  id_operator  ... origin_bonus  totalcosts  finalcosts
    1914     2701        Basel          624  ...          0.0        13.0        14.0
    [1 rows x 8 columns]
    """
    # Retrieve license key
    load_dotenv()
    if 'API_VESE_KEY' not in os.environ:
        license_key=get_vese_key()
        if not license_key:
            raise UserWarning("You need a key from VESE to access the injection prices")
    else:
        license_key = os.environ["API_VESE_KEY"]
    if len(str(year)) == 4:
        year = year % 100

    # Find the operator at that commune
    communes = get_providers_by_municipality_id(city)
    injection_prices = pd.DataFrame()
    for commune in communes.itertuples():
        url_grd = f'https://opendata.vese.ch/pvtarif/api/ClientService.php?mode=evu&evuId={commune.id_operator}' \
                  f'&year={year}&licenseKey={license_key}'
        response = rq.get(url_grd)
        if response.status_code == 200:
            json_data = response.content.decode('utf-8')
            json_data = json.loads(json_data)
            if not json_data['valid']:
                print(f'{json_data["code"]}: {json_data["details"]}')
                continue
        else:
            raise ExecutionError(f"{response.status_code}")

        try:
        # TODO: add a code to adapt the prices to the category given, as a function of what is defined
            commune_price = {'id_city': commune.id_city, 'municipality': commune.commune,
                             'id_operator': int(json_data['nrElcom']), 'operator': json_data['nomEw'],
                             'federal_tariff': float(json_data['energy1']), 'origin_bonus': float(json_data['eco1']),
                             'totalcosts': float(json_data['energy1']) + float(json_data['eco1'])
                             }
        except:
            continue
        commune_price = pd.DataFrame(commune_price, index=[commune.Index])
        injection_prices = pd.concat([injection_prices, commune_price])
    if tva is None:
        if year >= 2024:
            tva = 1.081
        else:
            tva = 1.077
    injection_prices['finalcosts'] = round(injection_prices['totalcosts'] * tva, 2)

    return injection_prices


def get_electricity_prices(city, year=2024, category=None, tva=None):
    """
    Builds a DataFrame with the electricity prices (demand and supply) ready to use for REHO.

    It calls `get_prices_from_elcom_by_city` and `get_injection_prices` and merges the two.

    Parameters
    ----------
    year : int
        Year from which the electricity prices must be retrieved.
    city : str/int
        Municipality from which the electricity prices must be retrieved. Can be in form of city ID or city name.
        If not given, queries the ELCOM database for the prices in every municipality.
    category : str
        Category from which the electricity prices must be retrieved.
        If not given, prices are given for every consumer category.
    tva : float
        Scaling factor for the resulting prices, initialized as the normal TVA.

    Returns
    -------
    pd.DataFrame with prices for the given parameters which columns are ['Year', 'City', 'Provider', 'Category', 'Elec_demand_cts_kWh', 'Elec_supply_cts_kWh'].

    See also
    --------
    get_prices_from_elcom_by_city : To retrieve the ELCOM prices by city.
    get_injection_prices : To obtain the injection prices instead.

    Examples
    --------
    >>> get_electricity_prices(year=2017, city='Genève')
        Year    City  ... Elec_demand_cts_kWh Elec_supply_cts_kWh
    0   2017  Genève  ...           22.216512               12.92
    1   2017  Genève  ...           21.887440               12.92
    2   2017  Genève  ...           19.197310               12.92
    3   2017  Genève  ...           21.596772               12.92
    4   2017  Genève  ...           19.367290               12.92
    5   2017  Genève  ...           16.895382               12.92
    6   2017  Genève  ...           19.316962               12.92
    7   2017  Genève  ...           21.598712               12.92
    8   2017  Genève  ...           23.155285               12.92
    9   2017  Genève  ...           23.548888               12.92
    10  2017  Genève  ...           21.866694               12.92
    11  2017  Genève  ...           20.781146               12.92
    12  2017  Genève  ...           22.345242               12.92
    13  2017  Genève  ...           17.155742               12.92
    14  2017  Genève  ...           15.900062               12.92
    [15 rows x 6 columns]

    """
    demand_prices = get_prices_from_elcom_by_city(year=year, city=city, category=category, tva=tva)
    supply_prices = get_injection_prices(city=city, year=year, category=category, tva=tva)

    electricity_prices = demand_prices[['Year', 'City', 'Provider', 'Category']].copy()
    electricity_prices['Elec_demand_cts_kWh'] = demand_prices['finalcosts']
    electricity_prices.loc[:, 'Elec_supply_cts_kWh'] = supply_prices['finalcosts'].iloc[0]

    return electricity_prices


if __name__ == '__main__':
    injection = get_injection_prices(year=2023, city='Basel')
    communes = get_electricity_prices(city='Genève', category=None, year=2017)
    # prices = get_prices_from_elcom(year=2023, canton='Geneva', category=None, export_path='../../elec_prices_2024.csv')
    id_commune = 177
    get_injection_prices(692)
    # url_commune = f'https://opendata.vese.ch/pvtarif/api/ClientService.php?mode=muni&idofs={id_commune}&licenseKey={license_key}'
