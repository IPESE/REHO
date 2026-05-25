# Renewable Energy Hub Optimizer

Renewable Energy Hub Optimizer (REHO) is a decision support tool for sustainable urban energy system planning.

It is developed by EPFL (Switzerland), within the Industrial Process and Energy Systems Engineering (IPESE) group.

REHO simultaneously addresses the optimal design and operation of capacities, catering to multi-objective
considerations across economic, environmental, and efficiency criteria. Its MILP framework, multi-objective
optimization, multi-scale adaptability, consideration of diverse end-use demands, and multi-energy integration drive
informed decision-making for renewable energy deployment in urban areas.

This documentation introduces REHO and highlights its key features and contributions to the field of
sustainable energy system planning.

```{image} images/district.svg
```

## Contents

::::{grid}

:::{grid-item-card} {octicon}`home` Overview
:link: sections/overview
:link-type: doc

Start with a quick summary of what is REHO and what it can do.
:::
::::

::::{grid}

:::{grid-item-card} {octicon}`book` Model
:link: sections/model/index
:link-type: doc

Describes the mathematical formulation behind the REHO model — building, district, and actors scales.
:::

:::{grid-item-card} {octicon}`package` Package structure
:link: sections/package_structure
:link-type: doc

Describes the content of the REHO package, with a description of functions you will come to use.
:::
::::

::::{grid}

:::{grid-item-card} {octicon}`rocket` Getting started
:link: sections/getting_started
:link-type: doc

Check out how to install and run REHO on your machine, setting up different configurations.
:::

:::{grid-item-card} {octicon}`code-review` Examples
:link: sections/examples
:link-type: doc

Still not sure how you should use REHO? Here are examples that include various features.
:::
::::

::::{grid}

:::{grid-item-card} {octicon}`git-branch` Releases
:link: sections/releases
:link-type: doc

Find here the code versions, the license, how to cite and the list of the related works.
:::
::::

```{toctree}
:maxdepth: 1
:hidden:

sections/overview
sections/releases
sections/model/index
sections/package_structure
sections/getting_started
sections/examples
sections/contribute
sections/appendix
```


## Downloading REHO

::::{grid}

:::{grid-item-card} Part-Time User? 😎
:padding: 3

REHO is available as a [PyPI package](https://pypi.org/project/REHO/)
and can be installed via pip with:

+++

```bash
pip install --extra-index-url https://pypi.ampl.com REHO
```
:::
::::

::::{grid}

:::{grid-item-card} Talented Developer? 🏄

REHO is an open-source and collaborative Python library.
Full code can be accessed from the [REHO repository](https://github.com/IPESE/REHO) and project cloned using the command:

+++

```bash
git clone https://github.com/IPESE/REHO.git
```
:::
::::


## Main contributors

```{image} images/logos/ipese-logo-black.svg
:width: 600
:height: 150
:align: right
:class: only-light
```

```{image} images/logos/ipese-logo-white.svg
:width: 600
:height: 150
:align: right
:class: only-dark
```

* Dorsan **Lepour** (2020-present)
* Cédric **Terrier** (2021-present)
* Joseph **Loustau** (2022-2024)
* Ziqian **Wang** (2025-present)

```{raw} html
<p>&nbsp;</p>
<p>&nbsp;</p>
```


## Funding projects

::::{grid} 2
:gutter: 2
:margin: 2 0 2 0

:::{grid-item-card} Services Industriels de Genève (SIG)
:text-align: center
:link: https://ww2.sig-ge.ch/
:link-type: url

```{image} images/logos/logo_sig.svg
:width: 100px
:align: center
```

2020–present
:::

:::{grid-item-card} Swiss Federal Office of Energy (SWEET–SWICE)
:text-align: center
:link: https://sweet-swice.ch/
:link-type: url

```{image} images/logos/logo_swice.jpg
:width: 300px
:align: center
```

2022–present
:::
::::
