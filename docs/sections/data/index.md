# Data reference

REHO turns reference data into an optimization problem, and the solution of that
problem into DataFrames. This section documents both ends of a run.

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} {octicon}`database` Input
:link: input
:link-type: doc

Every reference file shipped in `reho/data/` — technologies, energy layers, building
norms, mobility profiles, sky discretization: its columns, its units and where it
comes from, and how to replace it with your own data.
:::

:::{grid-item-card} {octicon}`table` Output
:link: output
:link-type: doc

Every DataFrame an optimization produces — design, operation, indicators: its index,
its columns and their units, when it is produced, and how to save and reload the
results.
:::
::::

```{toctree}
:maxdepth: 2
:hidden:

input
output
```
