from graphly.api_client import SparqlClient
import pandas as pd
from reho.paths import *
from reho.model.preprocessing.QBuildings import QBuildingsReader
import re

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


def get_prices_from_elcom(year=2023, canton=None, category=None, export_path=False):
    """
    Queries the prices from the ELCOM database. Define for which year, canton and consumer category.

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

    if isinstance(export_path, str):
        prices.to_csv(os.path.realpath(export_path))
    return prices


if __name__ == '__main__':
    prices = get_prices_from_elcom(category='H4', export_path='../../elec_prices_2023.csv')
    print('test')
