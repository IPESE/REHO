# Developer guide

REHO is an open-source, documented and collaborative decision support tool. Whether you
fix a bug, improve the documentation or add a feature, your contribution helps the whole
community. This guide gathers what you need to *change* REHO rather than run it: how a
run flows through the package, the conventions of the code, recipes for the most common
extensions, how to test and document a change, and how to get it merged.

Read {doc}`package_structure` first for the map of the package, and {doc}`model/index`
for the mathematical formulation.

:::{note}
Even without contributing, everyone is welcome to clone the repository and generate
results with REHO — without forgetting to {doc}`cite it <releases>`.
:::

---

## Anatomy of a run

```text
  QBuildingsReader.read_db / read_csv        initialize_grids + initialize_units
                  |                                          |
            qbuildings_data                            grids, units
                  \__________________  ________________/
                                     \/
                              REHO.__init__
                                     |
        +----------------------------+-----------------------------+
        |                            |                             |
  Infrastructure            return_local_data                eud_profiles
  sets & parameters      weather, typical periods      demand profiles (SIA)
        |                            |                             |
        +----------------------------+-----------------------------+
                                     |
                            method: which formulation?
                                     |
             +-----------------------+------------------------+
             |                                                |
   compact formulation                          Dantzig-Wolfe decomposition
   one SubProblem over                       MasterProblem  <--(configurations)--
   the whole district                              |        --(dual prices)--> SubProblem
             |                                     |                            per building
             +-----------------------+-------------+
                                     |
                          write_results -> df_* DataFrames
                                     |
                             calculate_KPIs
                                     |
                               reho.results
```

Concretely, {meth}`REHO.single_optimization <reho.model.reho.REHO.single_optimization>`
does one of two things depending on `method`:

- **compact formulation** (the default): one
  {class}`~reho.model.sub_problem.SubProblem` covering the whole district. Exact,
  but the MILP grows exponentially — roughly ten buildings is the practical limit.
- **decomposition** (`building-scale` or `district-scale`): a
  {class}`~reho.model.master_problem.MasterProblem` alternating between
  sub-problems that *propose* energy-system configurations and a master problem
  that *selects* a convex combination of them, exchanging dual prices at each
  iteration until the reduced costs stop improving.

`building-scale` is the degenerate case of the decomposition with a single master
iteration: each building is designed on its own, with no exchange between them.

---

## Conventions

### Naming

The Python layer mirrors the AMPL model, and the AMPL model uses the notation of the
publications. That is why `Scn_ID`, `Pareto_ID`, `df_Grid_t` and `Units_Mult` are
not PEP 8 — they are the names in the equations and in the results files, and
renaming them would break every user script and every saved result. New code
follows the surrounding style: AMPL-facing names keep the model's spelling,
everything else is `snake_case`.

A suffix `_t` marks a time-resolved quantity, `_SP` a sub-problem one, `_MP` a
master-problem one.

### File formats

AMPL code lives in `.mod` files only, and the data REHO ships are `.csv` files,
semicolon-separated, read by the Python layer and sent to AMPL as parameters — the
SIA 2024 norms, `sia2024_data.xlsx`, are the one exception. There are no AMPL `.dat`
or `.run` files: a value that the model derives from the data, such as the
temperature of a stream following the heating load, is a parameter defined in a
`.mod` file (see {data}`~reho.model.sub_problem.MODEL_STREAMS_TEMPERATURE`).

### Configuration is data

The three option dictionaries (`method`, `scenario`, `DW_params`) have their
defaults declared in {mod}`reho.model.options`, not scattered through the code. A
new option means one entry in {data}`~reho.model.options.DEFAULT_METHODS` and one
in {data}`~reho.model.options.METHOD_DESCRIPTIONS` — the documentation table is
generated from the latter, so it cannot drift.

Unknown options are reported rather than ignored:

```pycon
>>> REHO(..., method={'district_scale': True})
UserWarning: Unknown method option(s): 'district_scale' (did you mean 'district-scale'?). They will be ignored.
```

### Logging, not printing

REHO is a library: it never writes to `stdout` directly. Every module logs through
`logger = get_logger(__name__)`, and the application decides where those records
go:

```python
from reho.logger import configure_logging

configure_logging("DEBUG")          # verbose
configure_logging(enabled=False)    # silent
```

`method['print_logs']` is the shorthand the `REHO` class applies for you.

### Paths

Never hard-code a path. {mod}`reho.paths` exposes the location of everything the
package ships, and {func}`~reho.paths.file_reader` reads a tabular file whatever
its delimiter or format:

```python
from reho.paths import file_reader, path_to_infrastructure
units = file_reader(os.path.join(path_to_infrastructure, "building_units.csv"))
```

Two paths are resolved against the **current working directory** rather than the
package: `path_to_clustering` (`./data/clustering`) and `path_to_configurations`
(`./results/configurations`), which keeps the cached weather data of a run next to
its script. REHO's modules import these names when `reho` is imported, so a script
that needs another location changes its working directory *before* importing REHO.

### Imports

No `from x import *` inside the package: it hides where a name comes from and defeats
the linter. The modules that users import with `*` in their scripts keep an `__all__`,
so that those scripts keep working.

### Errors

Raise a specific exception with a message that says what to do about it. Never
`except:` — it swallows `KeyboardInterrupt` — and never `raise "a string"`, which
raises a `TypeError` instead of the intended error.

### Docstrings

Every public function, class and method has a docstring in the NumPy style, with the
unit of every physical quantity. The {ref}`api-reference` renders them in full, and the
documentation build fails on a malformed one.

---

## Extending REHO

(adding-a-technology)=
### Adding a technology

A technology is three things: **data** (what it costs, what it connects to), a
**model** (its equations), and a **registration** (when to load that model).

#### 1. Declare it in the data

Add a row to `reho/data/infrastructure/building_units.csv` (or
`district_units.csv`), following {ref}`tbl-units-schema`. The critical fields are:

- `UnitOfType`: the family name. This is the key the registry will use.
- `UnitOfLayer`: every layer the unit touches, including `HeatCascade` for thermal
  units. A unit whose layers are not all initialized is silently dropped.
- `StreamsOfUnit` with `stream_Tin` / `stream_Tout`: the heat-cascade streams, if any.
  A stream whose temperatures vary, with the heating load for instance, is listed in
  {data}`~reho.model.sub_problem.MODEL_STREAMS_TEMPERATURE` with the model parameters
  that hold them.

#### 2. Write the AMPL model

Create `reho/model/ampl_model/units/my_unit.mod`. Follow an existing file of the
same nature — `ng_boiler.mod` for a simple converter, `heatstorage.mod` for a
storage, `heatpump.mod` for a temperature-dependent one. The file declares its own
parameters and constraints over `UnitsOfType['MyUnit']`, and must not assume
anything about which other technologies are present.

#### 3. Register it

Add one entry to the appropriate registry in {mod}`reho.model.ampl_interface`:

```python
BUILDING_UNIT_MODELS = {
    ...
    "MyUnit": "my_unit.mod",
}
```

Insertion order is the order AMPL reads the files, so append rather than insert
unless the model genuinely depends on another being read first.

#### 4. Check it

The test-suite verifies the three parts agree, without needing a solver:

```bash
pytest reho/test/test_ampl_interface.py reho/test/test_data.py -q
```

`test_every_building_unit_type_has_a_model` fails if the CSV declares a
`UnitOfType` that no registry knows about — that is, if step 3 was forgotten.

Then run an actual optimization with the unit enforced:

```python
scenario['enforce_units'] = ['MyUnit']
```

---

### Adding an energy layer

1. Add a row to `reho/data/infrastructure/layers.csv` ({ref}`tbl-layers-schema`),
   with its tariffs, emission factors and network capacity.
2. Reference it from the `UnitOfLayer`, `Units_flowrate_in` and
   `Units_flowrate_out` of the technologies that use it.
3. Activate it in the run script — a layer absent from `initialize_grids` does not
   exist for the model, and every unit that needs it is dropped:

```python
grids = initialize_grids({'Electricity': {}, 'Hydrogen': {}, 'CO2': {}})
units = initialize_units(scenario, grids)   # after the grids, always
```

The AMPL model handles resource layers generically through the `ResourceBalance`
layer type, so a new carrier needs no new equation — only the technologies that
convert it do.

---

### Adding a KPI

Indicators are computed in {mod}`reho.model.postprocessing.KPIs` from the result
DataFrames, not from the AMPL model. Write a `postcompute_*` function that takes
the frames it needs and returns a DataFrame indexed by `Hub` (including a
`Network` row), then concatenate it in
{func}`~reho.model.postprocessing.KPIs.calculate_KPIs`. Document the new column in
{doc}`data/output`.

Computing indicators after the fact — rather than as AMPL variables — keeps them
out of the MILP, so adding one costs nothing in solve time and can be done on
results that are already saved.

---

(testing)=
## Testing

```bash
pytest reho/test -m "not slow"        # offline: no AMPL license needed
REHO_RUN_EXAMPLES=1 pytest reho/test  # full: runs every example script
```

The offline tier is what CI runs on every push. The tests that need a license, a
solver, the QBuildings database or the network are marked `slow`, and `needs_ampl`
or `needs_network`. The offline tier covers:

| File | What it protects |
|---|---|
| `test_import.py` | Every module imports, with no circular dependency |
| `test_options.py` | Option defaults, coupling rules and typo detection |
| `test_paths.py` | Path resolution, delimiter detection, file reading |
| `test_data.py` | Integrity of the shipped data files and their invariants |
| `test_ampl_interface.py` | Registries, AMPL files and data catalogue agree |
| `test_infrastructure.py` | Sets and parameters built from a known case |
| `test_preprocessing.py` | Typical periods match their medoid days, SIA heat gains, cache versioning |
| `test_decomposition.py` | Objective weights of the sub-problems in the decomposition |
| `test_postprocessing.py` | Indicators, sensitivity-analysis records, AMPL parameter extraction |

When changing anything that could affect the numbers, run at least one example
before and after and compare the results: identical output is the evidence that a
refactoring was behaviour-preserving, and a difference should be explained in the
pull request.

---

## Documentation

The documentation consolidates the knowledge generated by the REHO community. It is
built with Sphinx from the `docs/` directory and from the docstrings, and everyone is
welcome to improve it.

To build it locally:

```bash
pip install -r docs/requirements.txt
sphinx-build -b html -W --keep-going docs docs/_build/html
```

`-W` turns warnings into errors, as the continuous integration does: a broken
cross-reference fails the build rather than silently degrading the published site.

Some content is generated rather than written: the option tables of {ref}`tbl-methods`
come from {mod}`reho.model.options`, and the {ref}`api-reference` from the docstrings.
Edit the source, not the generated file.

If you are not familiar with Sphinx, see
[Getting started with Sphinx](https://docs.readthedocs.io/en/stable/intro/getting-started-with-sphinx.html).

---

(contributing)=
## Contributing

Besides this documentation, two platforms support the development of REHO: the GitHub
repository and the Mattermost channel.

### Repository

The [GitHub repository](https://github.com/IPESE/REHO) holds the code, the default
data, the example scripts and the documentation. It is also where bugs and new features
are tracked and discussed.

**People involved**

- **Administrators**: responsible for ensuring the repository rules are respected. They
  have most rights and manage the permissions of the other users.
- **Developers**: contribute new features on separate branches, and take part in
  peer reviews.
- **Users**: contribute by forking the code, producing results, and giving feedback on
  the tool.

**Branches**

- `main`: a stable and interoperable version of the code. Protected branch: only
  *Administrators* can push.
- `documentation`: additions and corrections to the documentation, whether `.md` files
  or docstrings. Anyone can push.
- **Others**: used by *Developers* to develop advanced features together, or by *Users*
  to generate results.

### Reporting issues

An issue can report a bug, but also suggest an enhancement or a new feature: it is the
place to discuss any idea or question related to REHO. To report one:

1. Navigate to the [Issues section](https://github.com/IPESE/REHO/issues) of the
   repository.
2. Click on the green "New Issue" button.
3. Describe the problem or the suggestion.
4. Always specify an *Assignee* and a *Label*.
5. Submit the issue.

:::{warning}
Review the existing issues first, to prevent duplicates, and give enough details for
the community to understand and address your concern.
:::

### Pull requests

Everyone can contribute to the development by:

1. Creating a branch from the [main branch](https://github.com/IPESE/REHO/tree/main);
2. Developing the code;
3. Opening a pull request in the [Pull requests section](https://github.com/IPESE/REHO/pulls);
4. Getting it accepted by an Administrator.

Before opening the pull request, run the checks of the continuous integration, which runs
them again on every push:

```bash
pytest reho/test -m "not slow"                               # see Testing
ruff check reho --select F,E9                                # undefined names, syntax errors
sphinx-build -b html -W --keep-going docs docs/_build/html   # see Documentation
```

If the change could affect the results, compare them before and after, as described in
{ref}`testing`.

### Communication

The [REHO community on Mattermost](https://ipese-mattermost.epfl.ch/signup_user_complete/?id=6ukmwrxfufgmdcajm8ok6krfxo&md=link&sbr=su)
is the place to chat quickly with other users and developers, and to contact the
Administrators directly (@dorsan or @cedric_terrier) with any question.
