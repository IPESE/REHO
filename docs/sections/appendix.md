# Appendix

In REHO, most of the model parameters can be given through additional files. However, there are default values
already implemented in the model. This appendix attempts to report them.

## Units

To define the units' costs, the price per unit installed and the unit lifetime are considered.
They are reported in Tables {ref}`tbl-building-units-csv` and {ref}`tbl-district-units-csv`.

(tbl-building-units-csv)=
```{csv-table} Building units default specifications
:file: ../../reho/data/infrastructure/building_units.csv
:header-rows: 1
:delim: ;
:class: longtable
```

(tbl-district-units-csv)=
```{csv-table} District units default specifications
:file: ../../reho/data/infrastructure/district_units.csv
:header-rows: 1
:delim: ;
:class: longtable
```

## Grids

(tbl-grid)=
```{csv-table} Grid default specifications
:file: ../../reho/data/infrastructure/layers.csv
:header-rows: 1
:delim: ;
:class: longtable
```

## Mobility

(tbl-dailyprofiles)=
```{csv-table} Metadata of hourly daily profiles for the mobility sector
:file: ../../reho/data/mobility/dailyprofiles_metadata.csv
:header-rows: 1
:delim: ,
:class: longtable
```

```{figure} ../images/externalexchanges.svg
:width: 600px
:align: center
:name: fig-mob1

A focus on mobility units and streams at the district-level
```
