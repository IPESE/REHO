from reho.paths import *
from reho.model.preprocessing.QBuildings import QBuildingsReader

import re
import time
from datetime import date, datetime
from typing import Dict, Optional, Union
import geopandas as gpd
import pandas as pd
import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter
from shapely import wkt

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

    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
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


def get_prices_from_elcom(year=2024, canton=None, category=None, tva=None, export_path=None):
    """
    Queries the electricity retail prices from the ELCOM database.
    Year, canton and consumer category can be specified. A QBuildingsReader object can be passed to 'canton' for automatic localization.
    TVA is applied by default or can be adapted as a scaling factor.

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


if __name__ == '__main__':
    prices = get_prices_from_elcom(year=2023, canton='Geneva', category=None, export_path='../../elec_prices_2024.csv')
