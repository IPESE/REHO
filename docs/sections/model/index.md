# Model

REHO models urban energy systems at three nested scales, each building on the previous one.
The core idea is the **energy hub** concept: a set of conversion and storage technologies that
interface local resources and imported energy supplies with end-users' energy services.

```{figure} ../../images/model/ch2_overview.png
:align: center
:width: 90%

The three modelling scales in REHO: Building, District, and Actors.
```

---

## Three modelling scales

::::{grid} 3
:gutter: 3

:::{grid-item-card} 🏠 Building model
:link: building
:link-type: doc

Single-building MILP for optimal design and operation of energy conversion and storage
technologies. Includes thermal dynamics, multi-objective optimization, and renovation decisions.
:::

:::{grid-item-card} 🏙️ District model
:link: district
:link-type: doc

Dantzig–Wolfe decomposition extends the building model to a district of many buildings.
Adds district heating/cooling networks, mobility services, and grid reinforcement.
:::

:::{grid-item-card} 👥 Actors model
:link: actors
:link-type: doc

Multi-actor framework layered on top of the district model. Explicitly represents tenants,
landlords, energy community managers, distribution system operators, and authorities.
:::

::::

---

## How the scales interact

The three layers are **not independent**: each higher-scale model inherits and extends the one below.

```{figure} ../../images/model/ch2_graphical_overview.png
:align: center
:width: 85%

Graphical overview of the building-scale model (Chapter 2 of the reference thesis).
```

```{figure} ../../images/model/ch3_graphical_overview.png
:align: center
:width: 85%

Graphical overview of the district-scale model (Chapter 3 of the reference thesis).
```

```{figure} ../../images/model/ch4_graphical_overview.png
:align: center
:width: 85%

Graphical overview of the actors model (Chapter 4 of the reference thesis).
```

---

## Notation convention

Throughout the model documentation the following typographic conventions are used:

| Convention | Meaning |
|---|---|
| **Bold** variable, e.g. $\boldsymbol{f}_{b,u}$ | Optimization decision variable |
| Regular, e.g. $F_u^{\max}$ | Fixed parameter |
| $\dot{E}$ | Power [kW] |
| $E$ | Energy [kWh] |
| $\dot{Q}$ | Thermal power in the heat cascade [kW] |
| Superscript $+$ | Outgoing flow (supply, production, export) |
| Superscript $-$ | Incoming flow (demand, consumption, import) |

Main index sets used across all scales:

| Set | Symbol | Description |
|---|---|---|
| Buildings | $\mathbb{B}$ | $b \in \mathbb{B}$ |
| Energy layers | $\mathbb{L}$ | $l \in \mathbb{L}$ |
| Technologies | $\mathbb{U}$ | $u \in \mathbb{U}$ |
| Typical periods | $\mathbb{P}$ | $p \in \mathbb{P}$ |
| Timesteps | $\mathbb{T}$ | $t \in \mathbb{T}$ |
| Configurations | $\mathbb{F}$ | $f \in \mathbb{F}$ (district scale) |
| District units | $\mathbb{U_D}$ | $u_d \in \mathbb{U_D}$ (district scale) |

---

```{toctree}
:maxdepth: 2
:hidden:

building
district
actors
```
