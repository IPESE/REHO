from scipy.io import readsav
import pyreadstat

from reho.model.reho import *


if __name__ == '__main__':
    filepath = "data/mobility/Daten_März_2023.sav"
    df, meta = pyreadstat.read_sav(filepath)