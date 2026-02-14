---
title: Climate Equity Concepts
description: Foundational concepts for fair share allocation approaches
search:
  boost: 2
---

# Climate Equity Concepts

This page introduces equity concepts that inform fair-shares allocation approaches. The goal is to help you understand the reasoning behind different approaches, not to prescribe which principles to adopt.

For implementation details, see [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/). For mathematical formulations, see the API Reference for [budgets](https://setupelz.github.io/fair-shares/api/allocations/budgets/) and [pathways](https://setupelz.github.io/fair-shares/api/allocations/pathways/).

!!! note "Scope and limitations"

    This documentation draws on a working subset of the climate equity literature (currently ~30 papers). It is not comprehensive — the sources cited here are illustrative examples from a much broader scholarly conversation, and we welcome corrections and suggestions. See [References](https://setupelz.github.io/fair-shares/science/references/) for the current bibliography.

---

## Principles and Ethical Grounding

Allocation approaches operationalize principles drawn from several traditions in distributive justice. The table below maps the principles used in fair-shares to their ethical grounding and code-level implementation. This is necessarily a simplification — the literature contains richer and more contested accounts than any summary table can capture.

### Overview

| Principle                        | Core Question                                             | Draws From                                                       | Where in fair-shares                                                |
| -------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Equal per capita entitlement** | Does each person have equal rights to the atmosphere?     | Egalitarianism [Caney 2009; Bode 2004]                           | `equal-per-capita-*` approaches                                     |
| **Historical responsibility**    | Should past emissions reduce future entitlements?         | Corrective justice, polluter pays [Meyer 2013; Shue 2015]        | `allocation_year`; `responsibility_weight` in `per-capita-adjusted` |
| **Ability to pay**               | Should wealthier countries bear more of the burden?       | Capabilities approach [Caney 2010; Baer 2009]                    | `capability_weight` in `per-capita-adjusted`                        |
| **Protection of basic needs**    | Should subsistence emissions be shielded from mitigation? | Sufficientarianism, right to development [Shue 2014; Meyer 2013] | Gini-adjusted approaches with income floor                          |

These principles are often combined. **CBDR-RC** (Common But Differentiated Responsibilities and Respective Capabilities), the cornerstone of the UNFCCC [Okereke 2016; Rajamani 2021], combines historical responsibility with ability to pay. The Paris Agreement added "in light of different national circumstances" [Rajamani 2021]. In fair-shares, CBDR-RC can be operationalized through parameter combinations such as early allocation year + capability adjustment (see [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/#parameters)).

**Additional influences:** Unjust enrichment [Heyward 2021; Pickering 2012] provides independent grounding for historical responsibility — including cases where past emitters could not have known the consequences. The no-harm principle and duty to preserve physical preconditions [Shue 2015] provide general justification for mitigation action without mapping to specific allocation formulas. Prioritarianism and limitarianism inform theoretical debates but are not directly operationalized.

### Equal Per Capita Entitlement

Grounded in egalitarianism — the view that all humans have equal moral status and therefore equal claims to shared resources [Caney 2009; Bode 2004]. Baer 2013 grounds this in cosmopolitan egalitarianism, treating individuals (not nations) as the fundamental moral units. Some authors critique equal per capita approaches as focusing on the wrong distribuendum — arguing that what matters is capabilities to meet needs, not emission rights per se [Caney 2021; Dooley 2021].

**Operationalized in:** `equal-per-capita-budget`, `equal-per-capita` pathway (see [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/#example-configurations-budget))

**Further reading:** Caney 2009, Bode 2004, Baer 2013, Matthews 2016

### Historical Responsibility

Grounded in corrective justice and the polluter pays principle. The long atmospheric lifetime of CO₂ means past emissions continue affecting the climate system, making cumulative accounting scientifically justified [Matthews 2016]. How to account for historical emissions — and from what start date — is one of the most debated questions in the literature (see Meyer 2013 for a treatment of the arguments). Pickering 2012 and Truccone-Borgogno 2022 develop an unjust enrichment framing that supports historical accountability independent of proving fault. Meyer 2013 proposes a benefits-based redistribution framing that sidesteps the non-identity problem.

**Operationalized in:** Two mechanisms. First, **early allocation year**: setting `allocation_year` to an early date (e.g., 1850) works with any approach. Second, **responsibility weight**: `responsibility_weight` in `per-capita-adjusted` approaches applies a multiplicative adjustment based on per-capita historical emissions. See [Historical Responsibility](https://setupelz.github.io/fair-shares/science/allocations/#historical-responsibility).

**Further reading:** Shue 2015, Meyer 2013, Matthews 2016, Heyward 2021, Morrow 2017

### Ability to Pay

Grounded in the capabilities approach (following Sen and Nussbaum), which focuses on what people are able to do and be [Klinsky 2018; Okereke 2016]. In fair-shares, this broad tradition is operationalized through the narrower "ability to pay" indicator (GDP per capita) as a proxy — a simplification that does not capture the full scope of the capabilities framework. This is a forward-looking principle that does not depend on past actions [Heyward 2021].

**Operationalized in:** `capability_weight` in `per-capita-adjusted` approaches (see [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/#parameters)).

**Further reading:** Caney 2010, Baer 2009, Morrow 2017, Klinsky 2018

### Protection of Basic Needs

Grounded in sufficientarianism — ensuring everyone meets a basic threshold of well-being [Meyer 2013; Zimm 2024] — and the right to development [Okereke 2016]. The literature distinguishes between subsistence emissions (necessary for basic needs) and luxury emissions (discretionary consumption), arguing they are not morally equivalent [Shue 2014; Baer 2009].

**Operationalized in:** Gini-adjusted approaches with income floor parameter (see [Gini Adjustment](https://setupelz.github.io/fair-shares/science/allocations/#gini-adjustment))

**Further reading:** Shue 2014, Baer 2009, Meyer 2013, Zimm 2024

---

## Core Practical Convergence

Shue 2015 argues that several independent principles converge toward the same practical conclusions about who should bear climate responsibility:

| Principle                        | Grounding                                            | Application                               |
| -------------------------------- | ---------------------------------------------------- | ----------------------------------------- |
| **Contribution** (Polluter Pays) | Caused the problem through emissions                 | Past emissions create current obligation  |
| **Benefit** (Beneficiary Pays)   | Gained from the problem through economic development | Inherited infrastructure justifies burden |
| **Ability to Pay** (Capability)  | Became able to act due to the problem                | Industrialization created capacity        |

The argument is that for nations ranking high on all three measures, the duty to act is "overdetermined" — supported by multiple independent lines of reasoning. This convergence is influential but not uncontested; see Shue 2015 for the full argument and its limitations.

---

## Key Distinctions

Methodological choices in fair shares analysis. See [Allocations](https://setupelz.github.io/fair-shares/science/allocations/) for implementation details.

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

**TCRE (Transient Climate Response to Cumulative Emissions):** The approximately linear relationship between cumulative CO₂ emissions and temperature change [Matthews 2016]. This provides the scientific basis for treating cumulative emissions as the relevant metric. See IPCC AR6 WG1.

**Carbon Debt:** Matthews 2016 quantifies carbon debts 1990-2013 totaling 250 billion tonnes CO₂. For net-zero carbon debt frameworks, see Pelz 2025b.

---

## Approaches Debated in the Literature

Several approaches appear in climate policy discussions and have been subject to scholarly critique.

### Grandfathering

Allocating future emission entitlements based on current emission shares. Critiqued by multiple authors as rewarding past high emissions with no ethical basis [Kartha 2018; Dooley 2021; Morrow 2017; Caney 2009]. The `per-capita-convergence` approach includes grandfathering elements and is available in fair-shares for comparison; see [PCC](https://setupelz.github.io/fair-shares/science/allocations/#per-capita-convergence-pcc).

### BAU Deviation Framing

Treating deviation from business-as-usual emissions as a cost or sacrifice. Pelz 2025a argues this framing is inconsistent with CBDR-RC because it treats current emission levels as a baseline entitlement.

### Small Share Justification

Arguments of the form "We only emit X% of global emissions." Winkler 2020 notes this cannot be universalized and conflates total with per capita emissions.

---

## Philosophical Challenges

Climate equity reasoning confronts persistent theoretical difficulties, including the **non-identity problem** (if different policies had been pursued, different people would exist) and **intergenerational justice** (whether current generations bear responsibility for ancestors' emissions). Various responses have been proposed, including benefits-based framing [Meyer 2013; Heyward 2021] and sufficientarian thresholds [Meyer 2013; Zimm 2024]. These are active debates without settled answers. See Meyer 2013 and Caney 2018 for detailed discussion.

---

## Multi-Dimensional Justice

The literature identifies multiple dimensions of justice beyond the distributive focus of this tool:

| Dimension                 | In brief                                                                            | Role in fair-shares                                |
| ------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------- |
| **Distributive Justice**  | How benefits and burdens are allocated [Zimm 2024]                                  | Primary focus of allocation approaches             |
| **Procedural Justice**    | Fairness of decision-making processes [Klinsky 2018]                                | Outside scope of this tool                         |
| **Corrective Justice**    | Responses to historical wrongdoing [Zimm 2024]                                      | Informs historical responsibility framing          |
| **Recognitional Justice** | How actors are characterized shapes consideration of their interests [Klinsky 2018] | Transparency about value judgments supports this   |
| **Transitional Justice**  | How to sequence policy toward more just conditions [Zimm 2024]                      | Pathway allocations address the temporal dimension |

**Further reading:** Klinsky 2018, Okereke 2016, Zimm 2024

---

## Policy Context

Fair share allocations are increasingly referenced in climate litigation and policy analysis [Rajamani 2024]. For discussions of loss and damage, climate finance, and just transition, see Okereke 2016, Morrow 2017, Muttitt 2020, and [References](https://setupelz.github.io/fair-shares/science/references/).

---

## See Also

**Within fair-shares:**

- [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/) — Design choices for budget and pathway allocations
- [Other Operations](https://setupelz.github.io/fair-shares/science/other-operations/) — Harmonization, RCB pathways, validation
- [API Reference: Budgets](https://setupelz.github.io/fair-shares/api/allocations/budgets/) | [Pathways](https://setupelz.github.io/fair-shares/api/allocations/pathways/) — Mathematical formulations
- [country-fair-shares Guide](https://setupelz.github.io/fair-shares/user-guide/country-fair-shares/) — Practical guidance
- [References](https://setupelz.github.io/fair-shares/science/references/) — Complete bibliography with annotations

**Key starting points in the literature:**

- Shue 2015 — Core practical convergence argument
- Meyer 2013 — Historical emissions and intergenerational justice
- Caney 2021 — Climate Justice (Stanford Encyclopedia overview)
- Dooley 2021 — Ethical choices behind fair share quantifications
- Pelz 2025a — Entry points framework for NDC fairness
- Klinsky 2018 — Building equity into climate modelling
- Kartha 2018 — Cascading biases in allocation approaches
