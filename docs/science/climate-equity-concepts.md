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
| **Ability to pay**               | Should wealthier countries bear more of the burden?       | Distributive justice [Caney 2010; Caney 2021; Baer 2013]         | `capability_weight` in `per-capita-adjusted`                        |
| **Protection of basic needs**    | Should subsistence emissions be shielded from mitigation? | Sufficientarianism, right to development [Shue 2014; Meyer 2013] | Gini-adjusted approaches with income floor                          |

These principles are often in tension with each other and may lead to conflicting allocations. The tool operationalizes each principle without making normative claims about which should take priority — that is a political and ethical judgment for users.

These principles are often combined. **CBDR-RC** (Common But Differentiated Responsibilities and Respective Capabilities), the cornerstone of the UNFCCC [Okereke 2016; Rajamani 2021], combines historical responsibility with ability to pay. The Paris Agreement added "in light of different national circumstances" [Rajamani 2021] — a qualifier that may represent a substantive shift from the original UNFCCC meaning, introducing a dynamic element whereby responsibilities evolve as national circumstances change [Rajamani 2024]. In fair-shares, CBDR-RC can be operationalized through parameter combinations such as early allocation year + capability adjustment (see [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/#parameters)).

**Additional influences:** Unjust enrichment [Heyward 2021; Pickering 2012] provides independent grounding for historical responsibility — including cases where past emitters could not have known the consequences. The no-harm principle and duty to preserve physical preconditions [Shue 2015] provide general justification for mitigation action without mapping to specific allocation formulas. Prioritarianism and limitarianism inform theoretical debates but are not directly operationalized.

### Equal Per Capita Entitlement

Grounded in egalitarianism — the view that all humans have equal moral status and therefore equal claims to shared resources [Caney 2009; Bode 2004]. Baer 2013 grounds this in cosmopolitan egalitarianism, treating individuals (not nations) as the fundamental moral units. Some authors critique equal per capita approaches as focusing on the wrong distribuendum — arguing that what matters is capabilities to meet needs, not emission rights per se [Caney 2021; Dooley 2021].

**Operationalized in:** `equal-per-capita-budget`, `equal-per-capita` pathway (see [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/#example-configurations-budget))

**Further reading:** Caney 2009, Bode 2004, Baer 2013, Matthews 2016

### Historical Responsibility

**Note on terminology:** Historical responsibility is a temporal dimension, not a separate principle. It operationalizes the **Polluter Pays Principle (PPP)** — the underlying normative principle that those who caused climate harm should bear greater burdens — by applying it over time to cumulative past emissions. PPP is the principle; historical responsibility is how PPP is applied across time.

Grounded in corrective justice and the polluter pays principle. The long atmospheric lifetime of CO₂ means past emissions continue affecting the climate system, making cumulative accounting scientifically justified [Matthews 2016]. How to account for historical emissions — and from what start date — is one of the most debated questions in the literature (see Meyer 2013 for a treatment of the arguments). Pickering 2012 and Truccone-Borgogno 2022 develop an unjust enrichment framing that supports historical accountability independent of proving fault. Meyer 2013 proposes a benefits-based redistribution framing that sidesteps the non-identity problem.

**Operationalized in:** Two mechanisms. First, **early allocation year**: setting `allocation_year` to an early date (e.g., 1850) works with any approach. Second, **responsibility weight**: `responsibility_weight` in `per-capita-adjusted` approaches applies a multiplicative adjustment based on per-capita historical emissions. See [Historical Responsibility](https://setupelz.github.io/fair-shares/science/allocations/#historical-responsibility).

**Further reading:** Shue 2015, Meyer 2013, Matthews 2016, Heyward 2021, Morrow 2017

### Ability to Pay

Those with greater wealth can bear costs with less sacrifice of welfare, so the greater an agent's ability to pay, the greater the proportion of cost they should bear [Caney 2010; Caney 2021; Baer 2013]. A floor level of consumption is crucial to health and wellbeing, so only income above that floor should count as capacity to pay [Baer 2013]. This is a forward-looking principle that does not depend on past actions [Heyward 2021].

Note: the capabilities approach (following Sen and Nussbaum) is a separate concept, developed by Caney [2018] as a framework for **intergenerational justice** — the idea that each generation should have equal capabilities to pursue a good life. It should not be conflated with the ability-to-pay principle, which concerns the distribution of current mitigation burdens among contemporaries.

**Operationalized in:** `capability_weight` in `per-capita-adjusted` approaches (see [Allocation Approaches](https://setupelz.github.io/fair-shares/science/allocations/#parameters)).

**Further reading:** Caney 2010, Caney 2021, Baer 2013, Heyward 2021, Morrow 2017

### Protection of Basic Needs

Grounded in sufficientarianism — ensuring everyone meets a basic threshold of well-being [Meyer 2013; Zimm 2024] — and the right to development [Okereke 2016]. The literature distinguishes between subsistence emissions (necessary for basic needs) and luxury emissions (discretionary consumption), arguing they are not morally equivalent [Shue 2014; Baer 2009].

**Important clarification:** In fair-shares, the income floor modifies _capability calculations_ — how we assess a country's ability to bear mitigation costs. It does not create emission entitlements or exempt any country from the global net-zero constraint. The tension between subsistence protection and net-zero targets is an important caveat in the literature (see Shue 2014).

**Operationalized in:** Gini-adjusted approaches with income floor parameter (see [Gini Adjustment](https://setupelz.github.io/fair-shares/science/allocations/#gini-adjustment))

**Further reading:** Shue 2014, Baer 2009, Meyer 2013, Zimm 2024

### Beneficiary Pays Principle

Agents should pay to the extent they have benefited from emissions-generating activities [Caney 2021; Heyward 2021]. This principle addresses a key gap in the polluter pays approach: where past emitters are deceased, current generations still enjoy the benefits — infrastructure, capital accumulation, industrial capacity — produced by those emissions. Benefiting from an unjust arrangement weakens the case for avoiding liability even where ignorance was excusable [Caney 2021]. The principle is also grounded in unjust enrichment doctrine: wealthy nations have been enriched through emissions-intensive development that consumed atmospheric space at others' expense [Truccone-Borgogno 2022; Pickering 2012].

Relationship to the polluter pays principle: the two principles are complementary rather than competing. Polluter pays captures obligations arising from causal responsibility; beneficiary pays captures obligations arising from continuing to enjoy the fruits of that harm. Together they support a "triply hybrid" framework — alongside ability to pay — where independent lines of reasoning converge on the same conclusion about which nations bear the greatest duty to act [Shue 2015].

**Further reading:** Caney 2021, Heyward 2021, Truccone-Borgogno 2022, Pickering 2012, Shue 2015

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

| Aspect           | Without Adjustment                                                                                                         | With Gini Adjustment                                                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Definition**   | Uses national average GDP per capita as capability indicator                                                               | Adjusts GDP per capita using Gini coefficient to reflect distribution                                             |
| **Rationale**    | Simpler; data widely available                                                                                             | More accurate picture of actual population circumstances                                                          |
| **Implications** | Does not account for income distribution; countries with same average GDP but different inequality are treated identically | Recognizes that two countries with same GDP per capita but different Gini have different distributional realities |

---

## Scientific Foundations

**TCRE (Transient Climate Response to Cumulative Emissions):** The approximately linear relationship between cumulative CO₂ emissions and temperature change [Matthews 2016]. This provides the scientific basis for treating cumulative emissions as the relevant metric. See IPCC AR6 WG1.

**Carbon Debt:** Matthews 2016 quantifies carbon debts 1990-2013 totaling 250 billion tonnes CO₂. For net-zero carbon debt frameworks, see Pelz 2025a.

---

## Approaches Debated in the Literature

Several approaches appear in climate policy discussions and have been subject to scholarly critique.

### Grandfathering

Allocating future emission entitlements based on current emission shares. Caney [2009] calls grandfathering "morally perverse," and Dooley [2021] documents that it has "virtually no support among moral and political philosophers." Despite this, it dominates many studies that claim to be value-neutral. Moreover grandfathering is often embedded implicitly in "blended" approaches that combine it with equity principles [Kartha 2018] which must be treated with caution.

The `per-capita-convergence` approach includes grandfathering elements and is available in fair-shares for comparison; see [PCC](https://setupelz.github.io/fair-shares/science/allocations/#per-capita-convergence-pcc).

### BAU Deviation Framing

Treating deviation from business-as-usual emissions as a cost or sacrifice. Pelz 2025b argues this framing is inconsistent with CBDR-RC because it treats current emission levels as a baseline entitlement.

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

Fair share allocations are increasingly referenced in climate litigation and policy analysis [Rajamani 2024]. The ICJ 2025 advisory opinion affirms intergenerational equity as a principle of international environmental law; climate protection obligations are erga omnes (owed to the international community as a whole), and the applicable due diligence standard is "stringent" given the severity of the climate threat. For discussions of loss and damage, climate finance, and just transition, see Okereke 2016, Morrow 2017, Muttitt 2020, and [References](https://setupelz.github.io/fair-shares/science/references/).

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
- Pelz 2025b — Entry points framework for NDC fairness
- Klinsky 2018 — Building equity into climate modelling
- Kartha 2018 — Cascading biases in allocation approaches
