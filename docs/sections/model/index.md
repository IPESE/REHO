# Model

REHO models urban energy systems at three nested scales, each building on the previous one.
The core idea is the **energy hub** concept: a set of conversion and storage technologies
that interface local resources and imported energy supplies with end-users' energy services.
The three models are interdependent.

---

::::{grid} 1 1 3 3
:gutter: 3

:::{grid-item-card} Building Model
:link: building
:link-type: doc
:text-align: center

```{image} ../../images/model/ch2_overview.png
:align: center
:width: 65%
```

Single-building MILP for optimal design and operation of energy conversion and storage
technologies. Includes thermal dynamics, multi-objective optimization, and renovation.
:::

:::{grid-item-card} District Model
:link: district
:link-type: doc
:text-align: center

```{image} ../../images/model/ch3_overview.png
:align: center
:width: 100%
```

Dantzig–Wolfe decomposition for communities of buildings. Adds district heating/cooling
networks, local mobility services, and grid reinforcement decisions.
:::

:::{grid-item-card} Actors Model
:link: actors
:link-type: doc
:text-align: center

```{image} ../../images/model/ch4_overview.png
:align: center
:width: 80%
```

Multi-actor framework layered on the district model. Represents tenants, landlords, energy
community manager, DSO, and authorities with individual economic constraints.
:::

::::

::::{grid} 1 1 3 3
:gutter: 3

:::{grid-item}

```{image} ../../images/model/ch2_graphical_overview.png
:align: center
:width: 110%
:class: model-graphical-overview
```

<p style="text-align:center; font-size:0.85em; color:var(--pst-color-text-muted); margin-top:0.3rem;">
Building model &nbsp;·&nbsp; <em>click to zoom</em>
</p>
:::

:::{grid-item}

```{image} ../../images/model/ch3_graphical_overview.png
:align: center
:width: 90%
:class: model-graphical-overview
```

<p style="text-align:center; font-size:0.85em; color:var(--pst-color-text-muted); margin-top:0.3rem;">
District model &nbsp;·&nbsp; <em>click to zoom</em>
</p>
:::

:::{grid-item}

```{image} ../../images/model/ch4_graphical_overview.png
:align: center
:width: 95%
:class: model-graphical-overview
```

<p style="text-align:center; font-size:0.85em; color:var(--pst-color-text-muted); margin-top:0.3rem;">
Actors model &nbsp;·&nbsp; <em>click to zoom</em>
</p>
:::

::::

---

:::{admonition} Reference thesis
:class: tip

D. Lepour, *Renewable Energy Communities for the Energy Transition*, EPFL, 2026.
[→ Full text on Infoscience](https://infoscience.epfl.ch/entities/publication/38113cbf-62b1-4aef-b980-7a78fde52b7b)

The three models documented here are described exhaustively in the manuscript, with full
equations, figures, and methodological details: **Chapter 2** covers the Building model,
**Chapter 3** the District model, and **Chapter 4** the Actors model.
:::

---

## Notation convention

The following typographic conventions are used throughout the model documentation:

| Convention | Meaning |
|---|---|
| **Bold** variable, e.g. $\boldsymbol{f}_{b,u}$ | Optimization decision variable |
| Regular, e.g. $F_u^{\max}$ | Fixed parameter |
| $\dot{E}$ | Power [kW] |
| $E$ | Energy [kWh] |
| $\dot{Q}$ | Thermal power in the heat cascade [kW] |
| Superscript $+$ | Outgoing flow (supply, production, export) |
| Superscript $-$ | Incoming flow (demand, consumption, import) |

Index sets used across all scales:

| Set | Symbol | Description |
|---|---|---|
| Buildings | $\mathbb{B}$ | $b \in \mathbb{B}$ |
| Energy layers | $\mathbb{L}$ | $l \in \mathbb{L}$ |
| Technologies | $\mathbb{U}$ | $u \in \mathbb{U}$ |
| Typical periods | $\mathbb{P}$ | $p \in \mathbb{P}$ |
| Timesteps | $\mathbb{T}$ | $t \in \mathbb{T}$ |
| Configurations | $\mathbb{F}$ | $f \in \mathbb{F}$ (district scale) |
| District units | $\mathbb{U_D}$ | $u_d \in \mathbb{U_D}$ (district scale) |

```{toctree}
:maxdepth: 2
:hidden:

building
district
actors
```
