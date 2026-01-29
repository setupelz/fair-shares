---
title: Climate Equity Concepts
description: Foundational concepts for fair share allocation approaches
search:
  boost: 2
---

# Climate Equity Concepts

Foundational concepts for understanding fair share allocation approaches. For implementation details, see [Allocation Approaches]({DOCS_ROOT}/science/allocations/). For mathematical formulations, see the API Reference for [budgets]({DOCS_ROOT}/api/allocations/budgets/) and [pathways]({DOCS_ROOT}/api/allocations/pathways/).

---

## Ethical Traditions

Allocation approaches draw on traditions in distributive justice.

### Framework Overview

| Framework                 | Core Question                         | Directly Used in fair-shares? | Where                                      |
| ------------------------- | ------------------------------------- | ----------------------------- | ------------------------------------------ |
| **Egalitarianism**        | Do all people have equal moral worth? | Yes                           | `equal-per-capita-*` approaches            |
| **Capabilities Approach** | Who can afford mitigation?            | Yes (partially)               | `per-capita-adjusted` approaches via GDP   |
| **Responsibility**        | Who caused the problem?               | Yes                           | `allocation_year` parameter                |
| **Sufficientarianism**    | Should basic needs get priority?      | Yes                           | Gini-adjusted approaches with income floor |
| Corrective Justice        | How to rectify past wrongs?           | Informs framing               | Historical responsibility section          |
| Unjust Enrichment         | Should ill-gotten gains be disgorged? | Informs framing               | Historical responsibility section          |

**Other frameworks:** Prioritarianism (distributional priority to worst-off) and Limitarianism (capping maximum emissions) inform theoretical debates but are not directly operationalized. See Morrow 2017 for prioritarianism discussion; limitarianism remains a theoretical consideration without current implementation.

### Egalitarianism

**This is an ethical tradition that grounds the principle of equal rights to the atmosphere.**

**Definition:** All humans have equal moral status and therefore equal claims to shared resources [Caney 2009; Bode 2004].

**Rationale:** Since no person inherently deserves more access to atmospheric space than another, equal per capita distribution reflects fundamental equality of persons. Baer 2013 grounds allocation in cosmopolitan egalitarianism: individuals (not nations) are the fundamental moral units.

**Derived Principle:** Equal rights to the atmosphere (equal per capita entitlement to atmospheric space).

**Operationalized in:** `equal-per-capita-budget`, `equal-per-capita` pathway (see [Allocation Approaches]({DOCS_ROOT}/science/allocations/#example-configurations-budget))

### Sufficientarianism

**Definition:** Justice that attributes high priority to protecting basic rights of all people, establishing a threshold below which people should not fall [Meyer 2013; Zimm 2024].

**Rationale:** Provides threshold conception of harm that can address the non-identity problem: people are harmed if they fall below a sufficientarian threshold regardless of whether they would exist under alternative policies.

**Operationalized in:** Gini-adjusted approaches with income floor parameter (see [Gini Adjustment]({DOCS_ROOT}/science/allocations/#gini-adjustment))

### Capabilities Approach

**Definition:** A philosophical framework (following Sen and Nussbaum) encapsulating economic, social, and personal capabilities necessary to pursue decent livelihood and realize human rights [Okereke 2016; Klinsky 2018].

**Rationale:** Proposed as framework to operationalize CBDR-RC by providing concrete means to assess country obligations and support needs.

**Operationalized in:** The `capability_weight` parameter in `per-capita-adjusted` approaches operationalizes the narrower "ability to pay" principle using GDP-based indicators (see [Choosing an Allocation Approach]({DOCS_ROOT}/science/allocations/#parameters)).

### Corrective Justice

**Definition:** A framework focused on rectifying past wrongs. The Lockean Proviso requires when appropriating commons resources to leave "enough and as good" for others [Morrow 2017].

**Rationale:** Applied to climate, developed countries violated this proviso by consuming atmospheric space such that others cannot develop using fossil fuels.

**Operationalized in:** Historical responsibility adjustments in `per-capita-adjusted` approaches (see [Incorporating Historical Responsibility]({DOCS_ROOT}/science/allocations/#historical-responsibility))

### Unjust Enrichment

**Definition:** A legal doctrine providing strict liability basis for historical responsibility independent of culpability [Pickering 2012; Truccone-Borgogno 2022].

**Rationale:** Unlike polluter-pays arguments that may require proving fault, unjust enrichment applies even if early emitters were "excusably ignorant" of climate impacts. Developed countries received economic benefits from atmospheric overuse.

**Operationalized in:** Historical responsibility adjustments and benefits-based redistribution framing

---

## Foundational Principles

These principles translate ethical traditions into actionable allocation rules. For in-depth theoretical debates, see [References]({DOCS_ROOT}/science/references/).

### Equal Rights to Atmosphere

**Definition:** Each person globally has an equal entitlement to atmospheric space. The atmosphere is a finite shared resource where no individual has greater inherent claim than another [Caney 2009; Matthews 2016].

**Rationale:** Since no person inherently deserves more access to atmospheric space than another, equal per capita distribution reflects fundamental equality of persons.

**Operationalized in:** `equal-per-capita-budget` (see [Example Configurations]({DOCS_ROOT}/science/allocations/#example-configurations-budget))

### Polluter Pays (Historical Responsibility)

**Definition:** Countries should bear responsibility proportional to their cumulative historical contribution to greenhouse gas emissions [Meyer 2013; Shue 2015]. Past emissions continue to affect the climate system due to the long atmospheric lifetime of CO₂ (centuries to millennia), and benefits derived from past industrialization persist across generations.

**Rationale:** CO₂ persists for centuries, meaning past emissions are not truly "past" but continue affecting the climate system [Shue 2015].

**Operationalized in:** Two mechanisms. First, **early allocation year**: setting `allocation_year` to an early date (e.g., 1850) calculates "equal per capita since 1850" and works with any approach. Second, **responsibility weight**: using `responsibility_weight` in `per-capita-adjusted` approaches applies a multiplicative adjustment based on per-capita historical emissions. See [Incorporating Historical Responsibility]({DOCS_ROOT}/science/allocations/#historical-responsibility).

### Ability to Pay (Capability)

**Definition:** Mitigation effort should be allocated in proportion to economic or technological capability, with wealthier parties bearing greater burdens [Baer 2009; Morrow 2017; Caney 2010].

**Rationale:** Those with greater resources have greater ability to contribute without compromising basic needs. Wealthier nations have greater capacity to transform energy systems without compromising development goals [Caney 2010; Dooley 2021].

**Operationalized in:** `per-capita-adjusted-budget` with `capability_weight` (see [Choosing an Allocation Approach]({DOCS_ROOT}/science/allocations/#parameters))

### CBDR-RC

**Definition:** Common But Differentiated Responsibilities and Respective Capabilities: all countries share responsibility for addressing climate change but have different levels of obligation based on historical contributions, current capabilities, and development needs. Embedded in the UNFCCC 1992 as a cornerstone of the international climate regime [Okereke 2016; Rajamani 2021].

**Rationale:** Recognizes that while climate change is a global problem requiring collective action, countries have contributed differently to the problem and have different capacities to respond.

**Operationalized in:** Multiple parameter combinations. The simplest is **early allocation year + capability adjustment**, which provides Differentiated Responsibilities via historical accounting and Respective Capabilities via `capability_weight` adjustment. See [Choosing an Allocation Approach]({DOCS_ROOT}/science/allocations/#parameters).

### No-Harm Principle

**Definition:** The prohibition on inflicting harm that one can reasonably expect to know one is inflicting [Shue 2015]. A "pure" principle that operates independently of historical responsibility or capability arguments.

**Rationale:** Continuing emissions constitute ongoing harm, not merely failure to help. One's fair share is "whatever it takes to bring one's contribution to the harm to an end" [Shue 2015]. This provides a forward-looking, action-forcing rationale independent of historical debates.

**Operationalized in:** Provides general justification for mitigation action rather than specific allocation formula.

### Duty to Preserve Physical Preconditions

**Definition:** The duty to preserve fundamental physical conditions of human life, grounded in Anthropocene reality where humanity is now the most powerful force changing the planet [Shue 2015].

**Rationale:** In the Anthropocene, humanity has become the most powerful force changing the planet. Fractional risks of catastrophe must be taken seriously [Shue 2015].

**Operationalized in:** Provides existential dimension beyond fair allocation; supports precautionary approach to temperature targets rather than specific allocation formula.

### Right to Development

**Definition:** Developing countries have a right to economic development, which historically has required energy use and associated emissions [Okereke 2016].

**Rationale:** Constraining development pathways is inequitable when developed countries achieved prosperity through fossil fuels. This principle supports protecting emissions necessary for basic needs and development, undergirding the distinction between subsistence and luxury emissions.

**Operationalized in:** Supports subsistence emissions protections in Gini-adjusted approaches (see [Gini Adjustment]({DOCS_ROOT}/science/allocations/#gini-adjustment)).

### Subsistence vs. Luxury Emissions

**Definition:** Subsistence emissions are necessary for meeting basic needs, while luxury emissions are discretionary. Only income and emissions above subsistence thresholds should count toward mitigation capacity. The Greenhouse Development Rights framework uses a development threshold of $7,500-$8,500 PPP [Baer 2009; Baer 2013].

**Rationale:** Emissions required for basic survival (heating, cooking, essential transport) differ fundamentally from emissions associated with discretionary consumption. Mitigation burdens should fall primarily on luxury emissions.

**Operationalized in:** Gini-adjusted approaches with income floor parameter (see [Gini Adjustment]({DOCS_ROOT}/science/allocations/#gini-adjustment))

---

## Core Practical Convergence

Multiple independent moral principles, though conceptually distinct, converge toward the same conclusions about who should bear climate responsibility [Shue 2015]. Historical responsibility combines contribution (polluter pays), benefit (beneficiary pays), and ability to pay (became able due to problem) simultaneously. Initial duties for high-emitting, wealthy nations are "unconditional and overdetermined" from multiple principle sources—making the case "almost unimaginably unfair and greedy" to cause a problem, keep benefits, and avoid costs [Shue 2015]. See Shue 2015 for full discussion.

| Principle                        | Grounding                                            | Application                               |
| -------------------------------- | ---------------------------------------------------- | ----------------------------------------- |
| **Contribution** (Polluter Pays) | Caused the problem through emissions                 | Past emissions create current obligation  |
| **Benefit** (Beneficiary Pays)   | Gained from the problem through economic development | Inherited infrastructure justifies burden |
| **Ability to Pay** (Capability)  | Became able to act due to the problem                | Industrialization created capacity        |

---

## Key Distinctions

Methodological choices in fair shares analysis. See [Allocations]({DOCS_ROOT}/science/allocations/) for implementation details.

### Production vs. Consumption Accounting

| Aspect           | Production-Based                                                                                                  | Consumption-Based                                                                                        |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **Definition**   | Emissions attributed where produced (territorial)                                                                 | Emissions attributed where goods consumed                                                                |
| **Rationale**    | Emissions occur within national boundaries under national policy control; producer countries benefit economically | Consumer countries drive demand for emissions-intensive goods; wealthy nations have outsourced emissions |
| **Implications** | Favors countries that import manufactured goods (net importers show lower emissions)                              | Favors countries that export manufactured goods (net exporters show lower emissions)                     |

### Cumulative vs. Annual Emissions Framing

| Aspect           | Budget (Cumulative)                                                       | Pathway (Annual)                                                              |
| ---------------- | ------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **Definition**   | Atmosphere as finite resource with fixed remaining budget                 | Climate action as dynamic process with year-by-year fairness                  |
| **Rationale**    | Provides clear total constraint; scientifically grounded in TCRE          | Provides year-by-year guidance; can adapt to changing circumstances           |
| **Implications** | Answers "What is each country's fair share of a fixed cumulative budget?" | Answers "What is each country's fair share of emissions in each future year?" |

### Within-Country Inequality

| Aspect           | Without Adjustment                                              | With Gini Adjustment                                                                                              |
| ---------------- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Definition**   | Uses national average GDP per capita as capability indicator    | Adjusts GDP per capita using Gini coefficient to reflect distribution                                             |
| **Rationale**    | Simpler; data widely available                                  | More accurate picture of actual population circumstances                                                          |
| **Implications** | Treats high-inequality countries as more capable than warranted | Recognizes that two countries with same GDP per capita but different Gini have different distributional realities |

---

## Scientific Foundations

**TCRE (Transient Climate Response to Cumulative Emissions):** The approximately linear relationship between cumulative CO₂ emissions and temperature change provides scientific grounding for historical responsibility arguments—past emissions continue warming the planet [Matthews 2016]. See IPCC AR6 WG1 for detailed discussion.

**Carbon Debt:** Countries whose historical emissions exceeded their equitable share have accumulated climate debt. Matthews 2016 quantifies carbon debts 1990-2013 totaling 250 billion tonnes CO₂. For net-zero carbon debt frameworks, see Pelz 2025b.

---

## Policy Implementation

Fair share allocations increasingly inform climate litigation and policy [Rajamani 2024]. Courts now apply objective benchmarks (IPCC AR6 reduction pathways) to assess state obligations, with differentiated due diligence standards based on emissions and capacity. Many developed countries face negative remaining allocations under principled approaches aligned with 1.5°C [Pelz 2025a]. See [References]({DOCS_ROOT}/science/references/) for discussions of loss and damage (Okereke 2016), climate finance (Morrow 2017), and just transition frameworks (Muttitt 2020).

---

## Critiqued Approaches in the Literature

These approaches appear in climate policy discussions. The literature contains debates about their theoretical foundations.

### Grandfathering

**Definition:** Allocates future emission entitlements based on current emission shares.

**Critiques in the literature:**

- Kartha 2018 argues grandfathering rewards past high emissions and that including it alongside egalitarian approaches "embeds systematic bias" against poorer countries
- Morrow 2017 notes arguments for grandfathering appeal to efficiency and practicality rather than fairness principles
- Dooley 2021 argues combining grandfathering with egalitarian approaches is inconsistent

The `per-capita-convergence` approach includes grandfathering elements; see [PCC]({DOCS_ROOT}/science/allocations/#per-capita-convergence-pcc).

### BAU Deviation Framing

**Definition:** Treating deviation from business-as-usual (BAU) emissions as a cost or sacrifice [Pelz 2025a].

**Critiques in the literature:**

- Pelz 2025a argues this framing is inconsistent with CBDR-RC
- The framing assumes current emission levels are a baseline entitlement

### Small Share Justification

**Definition:** Arguments of the form "We only emit X% of global emissions" as justification for limited action [Winkler 2020].

**Critiques in the literature:**

- Winkler 2020 notes this argument cannot be universalized
- It conflates total emissions with per capita emissions

---

## Philosophical Challenges

Climate equity reasoning confronts persistent theoretical difficulties, notably the **non-identity problem** (if different policies had been pursued, different people would exist, complicating compensation claims) and **intergenerational justice** (whether current generations bear responsibility for ancestors' emissions). Fair-shares sidesteps these challenges through benefits-based framing (redistribution of undeserved advantages rather than compensation for harms) and sufficientarian thresholds (protecting basic rights regardless of counterfactual comparisons). For detailed discussion, see Meyer 2013, Caney 2009, and [References]({DOCS_ROOT}/science/references/).

---

## Multi-Dimensional Justice Framework

| Dimension                 | Definition                                                                                                                                                                                                                                                      | Role in fair-shares                                                                                  |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **Distributive Justice**  | How benefits and burdens are allocated. Involves two distinct choices: (a) what is distributed (metric: emissions, energy services, health outcomes) and (b) how it's distributed (pattern: egalitarian, prioritarian, sufficientarian, limitarian) [Zimm 2024] | Primary focus of fair-shares allocation approaches                                                   |
| **Procedural Justice**    | Fairness of decision-making processes and meaningful participation. Has both moral significance and instrumental value: fair processes lead to more legitimate outcomes.                                                                                        | Governance concern; allocation tools cannot directly solve                                           |
| **Corrective Justice**    | Responses to historical wrongdoing through restoration or compensation. Distinct from historical responsibility; focuses on remedy and restitution [Zimm 2024].                                                                                                 | Informs historical responsibility framing                                                            |
| **Recognitional Justice** | How we characterize people shapes our ability to consider their interests. Example: Characterizing developing countries as "emerging emitters" may obscure their low per capita emissions and historical under-utilization of atmospheric space.                | Transparent allocation calculations that make value judgments explicit support recognitional justice |
| **Transitional Justice**  | How policy sequencing approaches ideally just pathways over time. Concerns the manner and pace of moving from current unjust conditions toward equity targets [Zimm 2024].                                                                                      | Pathway allocations address temporal dimension                                                       |

See Klinsky 2018, Okereke 2016, Zimm 2024 for detailed discussion.

---

## Suggested Reading

For deeper exploration of concepts introduced above, organized by topic. Full citations in [References]({DOCS_ROOT}/science/references/).

### Foundational Principles

**Equal per capita allocation (grounded in egalitarian tradition):**

- Bode 2004 — Equal emissions per capita over time
- Caney 2009 — Justice and distribution of greenhouse gas emissions
- Baer 2013 — Greenhouse Development Rights framework

**Historical responsibility:**

- Shue 2015 — Core practical convergence (contribution, benefit, ability to pay)
- Meyer 2013 — Why historical emissions should count
- Matthews 2016 — Quantifying historical carbon and climate debts
- Pelz 2025b — Net-zero carbon debt frameworks

**Capability and ability to pay:**

- Caney 2010 — Duties of the advantaged
- Baer 2009 — Greenhouse Development Rights proposal
- Morrow 2017 — Fairness in allocating global emissions budget

**Corrective justice and unjust enrichment:**

- Pickering 2012 — Concept of climate debt
- Truccone-Borgogno 2022 — Duty of restitution
- Heyward 2021 — Beneficiary pays principle

### Equity in Practice

**Fair shares and national contributions:**

- Pelz 2025a — Entry points for assessing fair shares in NDCs
- Dooley 2021 — Ethical choices behind quantifications of fair contributions
- Rajamani 2021 — National fair shares within international environmental law
- Winkler 2020 — Equity in global stocktake under Paris Agreement

**Multi-dimensional justice:**

- Zimm 2024 — Justice considerations in climate research
- Klinsky 2018 — Building equity into 1.5°C modelling
- Okereke 2016 — Climate justice and international regime

**Policy implementation:**

- Rajamani 2024 — Interpreting Paris Agreement in normative environment
- ICJ 2025 — State obligations (Advisory Opinion)
- Muttitt 2020 — Principles for managed fossil fuel phase-out

### Methodological Debates

**Allocation approaches and critiques:**

- Kartha 2018 — Cascading biases against poorer countries
- Budolfson 2021 — Utilitarian benchmarks for emissions
- Pan 2003 — Emissions rights and transferability

**Philosophical challenges:**

- Caney 2018 — Justice and posterity (intergenerational justice)
- Shue 2014 — Climate Justice: Vulnerability and Protection (book)
- Caney 2021 — Climate Justice (Stanford Encyclopedia overview)

---

## Further Reading

### Allocation Approaches

- **[Allocations]({DOCS_ROOT}/science/allocations/):** Design choices for cumulative budget and annual trajectory allocations
- **[Other Operations]({DOCS_ROOT}/science/other-operations/):** Supporting operations (harmonization, RCB pathways, validation)

### Implementation

- **[API Reference: Budget Allocations]({DOCS_ROOT}/api/allocations/budgets/):** Mathematical formulations
- **[API Reference: Pathway Allocations]({DOCS_ROOT}/api/allocations/pathways/):** Mathematical formulations
- **[country-fair-shares Guide]({DOCS_ROOT}/user-guide/country-fair-shares/):** Practical guidance

### Academic Literature

- **[References]({DOCS_ROOT}/science/references/):** Complete bibliography with annotations
