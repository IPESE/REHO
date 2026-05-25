(sec_actors_model)=
# 👥 Actors Model

The actors model extends the district-scale optimization of {doc}`district` by explicitly
representing the **economic interests and interactions of the distinct stakeholders** of a
local energy community.  Rather than minimizing a single district-wide objective, the model
accounts for the individual financial constraints of each actor while searching for
configurations that are acceptable to all parties.

```{figure} ../../images/model/dual_framework.png
:align: center
:width: 90%
:name: fig_dual_framework

Multi-actor optimization framework: actor-specific ε-constraints couple the district master
problem with actor cost balances.
```

The formulation uses the same Dantzig–Wolfe decomposition as the district model, enriched
with:

- **Actor-specific cost balances** (equations for tenants, landlords, ECM, DSO)
- **ε-constraints per actor** that enforce minimum economic viability
- **Actor-weighted subproblem objectives** steered by actor-related dual variables
- **A cascaded optimization algorithm** that orchestrates the multi-actor iterations

---

## Actors identification

Five key actors are distinguished in the energy community:

| Actor | Role | Key decisions |
|---|---|---|
| **Tenants** | Occupants without ownership; end users of energy services | Energy consumption; accept or reject service prices |
| **Landlords** | Property owners; select and invest in building energy systems | Technology selection; investment in BES |
| **Energy Community Manager (ECM)** | Non-profit operator of community-scale infrastructure; sets internal prices | District-unit investment; internal pricing; energy arbitrage |
| **Distribution System Operator (DSO)** | Manages electricity distribution grid; sets network tariffs | Grid capacity investment; import/export tariffs |
| **Authorities** | Public bodies that allocate subsidies for decarbonization | Subsidy levels; policy targets |

:::{note}
**Adapting the actor decomposition**

The five actors above represent one specific illustration of the multi-actor framework,
chosen to capture typical stakeholder dynamics in European energy communities. The modular
design of the model allows it to be adapted to represent alternative interaction schemes
between existing actors, or to introduce entirely new actors and business models (e.g.,
energy cooperatives, peer-to-peer trading platforms, aggregators). Chapter 4 of the
reference thesis provides further discussion on the expected learning curve to adapt the
model and highlights avenues for future developments.
:::

---

## Actors interactions

```{figure} ../../images/model/actors_interactions.png
:align: center
:width: 90%
:name: fig_actors_interactions

Financial flows among the five actors.
```

Energy transactions within the district use **dynamic internal pricing**, while prices at
the district boundary (towards the DSO or external suppliers) are fixed exogenous tariffs.

### Tenants' costs

```{math}
:label: eq_tenant_cost
\boldsymbol{C}_{T,b}
= \boldsymbol{C}^{T \to L}_b + \boldsymbol{C}^{T \to ECM}_b + \boldsymbol{C}^{T \to ECM,mob}_b
\qquad \forall\, b \in \mathbb{B}
```

- Energy purchased from the ECM (district grid):

```{math}
\boldsymbol{C}^{T \to ECM}_b
= \sum_{f,l,p,t} c^{D,+}_{f,b,l,p,t}\,\dot{\boldsymbol{E}}^{\text{gr},+}_{f,b,l,p,t}\,d_p\,d_t
```

- Self-consumed energy produced by the landlord's installation:

```{math}
\boldsymbol{C}^{T \to L}_b
= \sum_{f,l,p,t} c^{SC}_{f,b,l,p,t}\,\dot{\boldsymbol{E}}^{SC}_{f,b,l,p,t}\,d_p\,d_t
```

- Mobility services (fixed price per demand):

```{math}
\boldsymbol{C}^{T \to ECM,mob}_b = \overline{D}_b \cdot c^{mob}
```

### Landlords' costs

Landlords recover investment costs through revenue from self-consumption and ECM feed-in:

```{math}
:label: eq_landlord_cost
\boldsymbol{C}_{L,b}
= \sum_{f} \boldsymbol{\lambda}_{f,b}\,C_{f,b}^{\text{inv}}
- \boldsymbol{C}^{T \to L}_b
- \sum_{f,l,p,t} c^{D,-}_{f,b,l,p,t}\,\dot{\boldsymbol{E}}^{D,-}_{f,b,l,p,t}\,d_p\,d_t
\qquad \forall\, b \in \mathbb{B}
```

A positive value of $\boldsymbol{C}_{L,b}$ means a net cost (under-recovery); the
ε-constraint on landlords guarantees sufficient return on investment.

### ECM cost balance

The ECM aggregates all internal transactions:

```{math}
:label: eq_ecm_cost
\boldsymbol{C}_{ECM}
= \sum_{u_d} \boldsymbol{C}^{\text{CAPEX}}_D
+ \sum_b \bigl(\boldsymbol{C}^{ECM \to L}_b - \boldsymbol{C}^{T \to ECM}_b - \boldsymbol{C}^{T \to ECM,mob}_b\bigr)
+ \boldsymbol{C}^{ECM \to DSO} - \boldsymbol{C}^{DSO \to ECM}
+ \boldsymbol{C}^{ECM \to Extern}
```

### DSO cost balance

```{math}
:label: eq_dso_cost
\boldsymbol{C}_{DSO}
= \boldsymbol{C}^{OPEX}_{el}
+ \boldsymbol{C}^{\text{CAPEX}}_{DSO}
+ \boldsymbol{C}^{DSO \to ECM}
- \boldsymbol{C}^{ECM \to DSO}
```

Grid reinforcement CAPEX is annualized as:

```{math}
\boldsymbol{C}^{\text{CAPEX}}_{DSO}
= \frac{i(1+i)^n}{(1+i)^n-1}
  \bigl(c^{\text{net,1}}_{el} + c^{\text{net,2}}_{el}\,\boldsymbol{E}^{\text{net,additional}}_{el}\bigr)
```

---

## Master problem

### Objective function

The master problem minimizes total district expenditures plus the **subsidies** required to
make every actor's balance feasible:

```{math}
:label: eq_mp_obj
\min\;\boldsymbol{C}^{\text{TOTEX}}
+ \sum_{b \in \mathbb{B}}\bigl(\boldsymbol{S}^T_b + \boldsymbol{S}^L_b\bigr)
+ \boldsymbol{S}^{ECM} + \boldsymbol{S}^{DSO}
```

Subsidies $\boldsymbol{S}^T_b$, $\boldsymbol{S}^L_b$, $\boldsymbol{S}^{ECM}$,
$\boldsymbol{S}^{DSO}$ are decision variables that represent the minimum public support
required to make each actor's participation economically rational.

### Actor ε-constraints

Each actor must achieve at least their individual rationality threshold, grounded in the
cooperative game theory concept of the **Core**:

```{math}
:label: eq_eps_tenant
\boldsymbol{C}_{T,b} - \boldsymbol{S}^T_b \le \epsilon^T_b
\qquad \forall\, b \in \mathbb{B}
```

```{math}
:label: eq_eps_landlord
\boldsymbol{C}_{L,b} + \boldsymbol{S}^L_b \ge \epsilon^L_b
\qquad \forall\, b \in \mathbb{B}
```

```{math}
:label: eq_eps_ecm
\boldsymbol{C}_{ECM} + \boldsymbol{S}^{ECM} \ge \epsilon^{ECM}
```

```{math}
:label: eq_eps_dso
\boldsymbol{C}_{DSO} + \boldsymbol{S}^{DSO} \ge \epsilon^{DSO}
```

Threshold interpretation:

- **Tenants** ($\epsilon^T_b$): total energy cost must not exceed the pre-retrofit
  status-quo cost — tenants only cooperate if they do not pay more than before.
- **Landlords** ($\epsilon^L_b$): return on investment must exceed the opportunity cost
  of capital (interest-dependent lower bound).
- **ECM** ($\epsilon^{ECM}$): net balance must remain non-negative (or above a minimum
  margin reflecting the ECM's cost of operation).
- **DSO** ($\epsilon^{DSO}$): net balance must remain non-negative.

:::{note}
**Cooperative game theory: the Core**

The ε-constraints encode **individual rationality** from cooperative game theory: each
actor must do at least as well in the cooperative energy community as they would
independently. The set of cost allocations satisfying all such constraints defines the
**Core**. By parametrically varying the thresholds, different fairness rules can be
explored — for example, tightening $\epsilon^T_b$ to prioritize lower tenant bills, setting
$\epsilon^{ECM} = 0$ for ECM cost neutrality, or fixing $\epsilon^{DSO}$ to ensure full
grid-cost recovery. This reveals trade-offs between social equity and system efficiency
along a Pareto set across actors.
:::

### Actor dual variables

The dual variables of the ε-constraints measure the sensitivity of the optimal cost to
each actor's financial threshold:

```{math}
:label: eq_actor_duals
\boldsymbol{\nu}^T_b = \frac{\Delta\,\text{obj}}{\Delta\,\epsilon^T_b},
\quad
\boldsymbol{\nu}^L_b = \frac{\Delta\,\text{obj}}{\Delta\,\epsilon^L_b},
\quad
\boldsymbol{\nu}^{ECM} = \frac{\Delta\,\text{obj}}{\Delta\,\epsilon^{ECM}},
\quad
\boldsymbol{\nu}^{DSO} = \frac{\Delta\,\text{obj}}{\Delta\,\epsilon^{DSO}}
```

These dual variables are passed to the subproblems to **steer configuration generation
toward solutions that alleviate binding actor constraints**.

---

## Subproblems

Each building SP objective is modified to account for the contribution of the new
configuration to each actor's financial balance, weighted by the actor dual variables:

```{math}
:label: eq_sp_actors_obj
\min\;\boldsymbol{C}_b^{\text{TOTEX}}
- \mu_b
- \nu^T_b\,\boldsymbol{C}_{T,b}
- \nu^L_b\,\boldsymbol{C}_{L,b}
- \nu^{ECM}\,\boldsymbol{C}^{ECM}_b
- \nu^{DSO}\,\boldsymbol{C}^{DSO}_b
```

The actor cost terms $\boldsymbol{C}_{T,b}$, $\boldsymbol{C}_{L,b}$, $\boldsymbol{C}^{ECM}_b$,
$\boldsymbol{C}^{DSO}_b$ are computed within the SP using the building's own energy flows
and the internal pricing structure. The dual variables $\nu$ act as economic weights: a
large $\nu^T_b$ means the master problem greatly benefits from reducing tenant costs, so
the SP will seek configurations with lower tenant bills.

---

## Cascaded optimization algorithm

```{figure} ../../images/model/cascaded_algorithm.png
:align: center
:width: 85%
:name: fig_cascaded_algo

Cascaded optimization algorithm for the multi-actor energy community model.
```

The algorithm builds on the Dantzig–Wolfe decomposition of {doc}`district` with three
phases:

**Phase 1 — Initiation (without actor constraints):**

1. Generate an initial pool of building configurations by solving single-objective or
   small Pareto-frontier building optimizations (no internal pricing, no actor coupling).
2. Solve a relaxed MP (no actor ε-constraints) to obtain initial dual variables
   $\boldsymbol{\pi}$, $\boldsymbol{\mu}$.

**Phase 2 — Iteration (with actor constraints):**

3. Solve the full MP (including actor ε-constraints) with the current configuration pool.
4. Extract actor dual variables $\boldsymbol{\nu}^T$, $\boldsymbol{\nu}^L$,
   $\boldsymbol{\nu}^{ECM}$, $\boldsymbol{\nu}^{DSO}$ and pass to all SPs.
5. Each building SP searches for the configuration with the most negative reduced cost
   under the actor-weighted objective {eq}`eq_sp_actors_obj`.
6. Add new configurations to the pool and re-solve the MP.
7. Repeat until no SP generates a negative reduced-cost configuration.

**Phase 3 — Finalization:**

8. Solve the final integer MP ($\boldsymbol{\lambda}_{f,b} \in \{0,1\}$).
9. Compute all actor cost balances and subsidy levels for the selected configuration.

:::{note}
The "cascaded" name reflects the sequential dependence: each MP solve depends on
configurations generated under the previous MP's dual variables, creating a cascade of
increasingly actor-aware configurations.
:::

---

:::{seealso}
**Multi-actor extension**

The actors model is a layered extension of the {doc}`District model <district>`, which is
itself built on the {doc}`Building model <building>`. All technical features — renovation,
mobility, grid reinforcement, and district heating/cooling networks — remain fully available
at this scale. Refer to the {doc}`Package structure <../4_Package_structure>` and
{doc}`Getting started <../5_Getting_started>` sections for practical usage.
:::
