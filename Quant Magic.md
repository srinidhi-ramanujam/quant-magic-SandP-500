
# Quant Magic

**Prepared for:** JP Morgan — Merchant Services Group  
**Date:** November 2025

> **Ascendion’s Quant Magic** — *Ascendion Confidential*

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Background / Problem Statement](#background--problem-statement)
- [Proposed Solution](#proposed-solution)
- [Business ROI & Benefits](#business-roi--benefits)
- [Differentiators & Innovation](#differentiators--innovation)
  - [Proprietary Azure Native Solution](#proprietary-azure-native-solution)
  - [Proven Expertise](#proven-expertise)
  - [Speed To Value](#speed-to-value)
  - [Future Ready Capabilities](#future-ready-capabilities)
  - [AI & Data](#ai--data)
- [Security](#security)
- [Commercial Potential](#commercial-potential)
- [Tech Stack](#tech-stack)
- [Reference Architecture (ASCII)](#reference-architecture-ascii)
- [Pilot Proposition](#pilot-proposition)
  - [Implementation Roadmap](#implementation-roadmap)
  - [Week 1: Assessment and Scoping](#week-1-assessment-and-scoping)
  - [Week 2 & 3: Ingestion and Proof of Concept (PoC)](#week-2--3-ingestion-and-proof-of-concept-poc)
  - [Week 4: Build and Demo](#week-4-build-and-demo)
  - [Week 4: Deliverables](#week-4-deliverables)
  - [Week 5: Outcomes](#week-5-outcomes)
- [Conclusion](#conclusion)
- [Quant Magic Cheat Sheet](#quant-magic-cheat-sheet)
  - [What Is It?](#what-is-it)
  - [How It Works](#how-it-works)
  - [Key Features](#key-features)
- [About the Authors](#about-the-authors)

---

## Executive Summary

Quant Magic is a production-ready, customized suite of bespoke AI-driven solutions that deliver end-to-end financial analytics using modern tools and natural language query capabilities, reducing time-to-insight from hours to minutes while ensuring governance, security, and scalability.  
It can be used by JPMC CFO Office and F&BM analysts as well as by customers of JPMC CIB Treasury Services to run complex and comprehensive financial analysis.  
Quant Magic was developed by Ascendion for a global financial institution and has been deployed in production since January 2025. Once built and customized by Ascendion and deployed in JPMC, Quant Magic’s IP will stay with JPMC.

---

## Background / Problem Statement

Complex financial data from diverse sources slows analysts and limits decision-making. Manual workflows and SQL queries constrain scalability, while siloed tools and compliance requirements create operational inefficiencies. Additionally, regulatory compliance and governance requirements introduce further friction to operations.

For example, if someone from the CFO Office needs to run a complex, comprehensive analysis of two different portfolios or an analysis across sectors, they would have to work with a Data Engineer to look up for the right data sources and run various SQL/NoSQL queries to fetch the data from the database, and then work with a Data Analyst to put the results into a visual form (PowerBI, Tableau, or some other Business Intelligence tool). This process can take days.

Examples of complex financial analyses:

1. Show Return on Equity trends for major Financial Services companies during the COVID years (2020–2024) and identify which companies showed highest volatility versus stability.  
2. Analyze long-term financial outperformance patterns across S&P 500 sectors from 2020–2024 by measuring ROE, profit margins, and growth trends. Which sectors demonstrate the most consistent financial sustainability and which companies within those sectors show superior operational efficiency?  
3. Which Technology companies have shown the most consistent profitability improvement between 2019–2023? Compare Apple, Microsoft, NVIDIA, Adobe, and Salesforce across profit margins, ROE, and growth consistency. Identify which companies demonstrate stable margin expansion versus high-growth volatility patterns.  
4. Analyze the free cash flow generation trends for Energy sector companies between 2020–2023, highlighting the impact of oil price volatility.

> *Note:* Ascendion is an AI-powered software engineering leader and a Preferred Supplier to JPMC since 2023 as part of its IT Professional Services (ITPS) program. For more on Ascendion, see: https://ascendion.com/who-we-are/

---

## Proposed Solution

Quant Magic reduces the time needed to produce such analysis by removing the need for a data engineer or analyst. The CFO Office or F&BM user can use Quant Magic to ask a question in natural language and Quant Magic will understand their language and lingo, ask clarifying questions, pull up the right data sources, put together a query, run the query, fetch the data, prepare a visual if the analysis needs it, and present it back to the user — all done in the span of just a few minutes. If the user wants to keep this for future usage, they can bookmark the analysis output. If the user needs to share the analysis, a PDF or Word report with the organization-specific template can be prepared.

As mentioned, Quant Magic can be consumed within the organization to improve financial analysis efficiencies and can also be commercialized and sold to corporate clients. A proposed implementation roadmap is outlined in the Pilot Proposition section below.

---

## Business ROI & Benefits

- Eliminates manual effort and fragmented tools, significantly reducing time-to-insight from hours to minutes. Delivers minutes-to-insight for analysts, reduces total cost of ownership (TCO) by 50–60%, and drives measurable productivity gains by replacing manual processes with AI-driven automation.  
- Governance, security, and compliance are built in, and can be built to scale seamlessly with Role-based Access Controls (RBAC) and data lineage tracking.  
- Provides exceptional financial insights and supports both strategic and tactical Q&A capabilities. A semantic layer ensures business-ready answers, making data actionable across the organization.  
- Bespoke customization, accuracy, sub-second latency, and modern tech stack.  
- Can be sold as a financial product to corporate clients of JPMC.

---

## Differentiators & Innovation

### Proprietary Azure Native Solution

- Domain-specific financial intelligence trained on U.S. SEC EDGAR data with 21,450+ financial metrics for S&P 500 companies (public domain dataset chosen for demo; bespoke implementations use client data).  
  - SEC EDGAR: https://www.sec.gov/edgar/searchedgar/companysearch.html  
- Institutional-grade accuracy with >90% evaluation pass rate across 129 comprehensive test scenarios.  
- Advanced AI reasoning capabilities (e.g., GPT‑5 compatible) with transparent cost tracking.

### Proven Expertise

- Production-ready system with 100% test coverage rate on complex financial queries.  
- Financial domain expertise covering XBRL standards, GAAP compliance, and regulatory requirements.  
  - XBRL International: https://www.xbrl.org/  
- Memory-optimized architecture handling enterprise workloads with <4 GB peak usage.

### Speed To Value

- Template-based fast path delivering sub-second responses for 70%+ of common queries.  
- Pre-built financial ratio calculations covering major investment analysis scenarios.  
- Immediate deployment with existing CLI tools and evaluation framework.

### Future Ready Capabilities

- Modular architecture supporting web interface expansion and API integration.  
- Batch processing capabilities for large-scale institutional analysis workflows.  
- Continuous learning system that improves accuracy and coverage over time.

### AI & Data

- **In-Context Learning (ICL):** Two knowledge bases — *Domain Knowledge* and *Instruction Set*. Both used for ICL with parameterized, grounded definitions (e.g., definition of FY, BU mappings) and few-shot examples (e.g., calculating the cash conversion cycle with a given formula and example).  
- **Selective LLM usage:** LLMs for language, Q&A, and semantic understanding; context retrieval, math, and financial calculations handled separately to ensure precision (e.g., fiscal year handling across companies).  
- Balances AI-driven insights with data privacy and customizability.

---

## Security

- Deployable on any Hyperscale Cloud provider approved by JPMC or on JPMC private Cloud, adhering to cybersecurity requirements.  
- All JPMC Data and PII remain inside JPMC environment, adhering to Data Security requirements.

---

## Commercial Potential

- Packaged as a financial product for corporate customers of JPMC.  
- Already deployed commercially at three major corporates (customers of the original global financial institution).  
- Deployments via stand-alone Deployment SOWs with milestones; a Core SOW governs common features deployable across clients. All SOWs executed between Ascendion and JPMC.

---

## Tech Stack

Quant Magic is built on an Azure-native pipeline that combines an OLAP database with a Parquet-based Lakehouse. Natural language query, powered by Azure OpenAI, allows analysts to “talk to data” for faster insights. The solution provides secure, end-to-end analytics fully within Azure, embedding governance, RBAC, and data lineage. By eliminating tool silos and automating workflows, it delivers insights in minutes, improving efficiency and scalability.

---

## Reference Architecture (ASCII)

```text
+=============================================================================+
|                     Security & Governance (RBAC, Lineage, Compliance)       |
|                                                                             |
|  Users & Channels                                                           |
|  -----------------                                                          |
|  [CFO Office] [F&BM Analysts] [CIB Clients] -> CLI / (future) Web / API     |
|                                                                             |
|  Data Sources                                                               |
|  ------------                                                               |
|  [Internal Finance DBs] [Market/SEC EDGAR] [Spreadsheets/Files]             |
|           |                                                                  |
|           v                                                                  |
|  Ingestion & Orchestration                                                   |
|  -------------------------                                                   |
|  [Connectors/ETL] -> [Validation] -> [Schema Mapping] -> [ICL KB Build]     |
|           |                                  |                               |
|           |                                  +-->  Knowledge Bases           |
|           |                                       - Domain Knowledge         |
|           |                                       - Instruction Set          |
|           v                                                                  |
|  Lakehouse & OLAP                                                            |
|  ----------------                                                            |
|  [Parquet Lakehouse]  <-->  [OLAP Star/Snowflake Schemas]                    |
|           |                  \                                               |
|           |                   \                                              |
|           |                    \-> [Precomputed Ratios / Templates]          |
|           v                                                                  |
|  Semantic Layer                                                              |
|  --------------                                                              |
|  [Business Terms, FY logic, BU mappings, Metrics Catalog]                    |
|           |                                                                  |
|           v                                                                  |
|  AI & Query Layer                                                            |
|  ----------------                                                            |
|  [Router] -> (Fast Path Templates)                                           |
|             -> (AI Path: Text → SQL → Text)                                  |
|                 [LLM(s): GPT‑5 / Anthropic / Gemini]                         |
|                 [Vector Store / Retrieval]                                   |
|                 [Deterministic Math/Finance Engines]                         |
|           |                                                                  |
|           v                                                                  |
|  Outputs                                                                     |
|  -------                                                                     |
|  [Sub‑second Answers] [Charts] [PDF/Word Reports] [APIs]                     |
|                                                                             |
|  Ops & Quality                                                               |
|  -------------                                                               |
|  [Evaluation Suite: 129 scenarios, >90% pass] [Cost Tracking] [Logging]     |
+=============================================================================+
```

---

## Pilot Proposition

As JPMC’s preferred IT Professional Services Supplier, Ascendion offers a co-engineering approach to build Quant Magic and tailor it to specific requirements and needs. We will outline an implementation scope and acceptance criteria, followed by drafting a Fixed-price Statement of Work (SOW) with defined outcomes (milestones) and timelines.

### Implementation Roadmap

The implementation begins with data ingestion, collecting, and centralizing diverse sources. Next, a structured OLAP/Parquet-based Lakehouse is built. Analysts can then use the “Talk to Data” interface to query data naturally. Finally, the solution is deployed with full governance, security, and scalability.

### Week 1: Assessment and Scoping

- Evaluate existing financial analysis workflows and pain points.  
- **Use Case Definition:** Identify high-impact scenarios for immediate ROI demonstration.  
- **Technical Requirements:** Assess infrastructure needs and integration requirements.  
- **Success Metrics Definition:** Establish clear KPIs for pilot success measurement.

### Week 2 & 3: Ingestion and Proof of Concept (PoC)

- **System Deployment:** Deploy production-ready Command-Line Interface (CLI) tools in the client environment.  
- **Data Ingestion:** Connect to financial data sources and ingest into custom OLAP schema.  
- **Custom Template Development:** Create client-specific query templates for key use cases.  
- **Domain-Specific Run Book:** High-level capabilities in Q&A form that the solution can support.

### Week 4: Build and Demo

- Fine-tune with domain knowledge and custom instruction set to ensure answers deliver as per expectation.  
- **Demo Playbook:** Showcase capability to deliver exceptional insights on financial queries.

### Week 4: Deliverables

- **Pilot Results Analysis:** Measure performance against defined success metrics.  
- **ROI Demonstration:** Quantify time savings, accuracy improvements, and cost reductions.  
- **User Training & Onboarding:** Train key stakeholders on system capabilities and usage.  
- **Commercial Framework:** Finalize pricing model and service level agreements (SLAs).

### Week 5: Outcomes

- **Immediate Value:** 70%+ reduction in financial analysis time with improved accuracy.  
- **Proven ROI:** Documented cost savings through automated insights and reduced manual research.  
- **Strategic Advantage:** Enhanced decision-making with AI-powered financial intelligence.  
- **Scalable Foundation:** Ready-to-expand platform supporting growing analytical needs.

---

## Conclusion

Quant Magic represents a transformative leap in financial analytics, combining AI-driven automation with enterprise-grade precision and scalability. Developed by Ascendion, the solution enables natural language queries, streamlines complex workflows, and delivers insights in minutes. With proven deployments, customizable architecture, and strong commercial potential, Quant Magic can empower JPMC teams and clients to make faster, smarter decisions. It’s not just a tool — it’s a strategic asset for future-ready financial intelligence.

---

## Quant Magic Cheat Sheet

### What Is It?

- **Instant Financial Analysis:** Ask questions in plain English and get professional insights in seconds.  
- **Complete S&P 500 Coverage:** 15.5m+ data points across 589 companies and 11 sectors.  
- **Enterprise-Grade Quality:** Institutional investment-grade analysis.  
- **Zero Learning Curve:** No training required — natural language interface.  
- **Cost-Effective Alternative:** Reduces expensive data engineering and research teams.

### How It Works

- **Layered multi‑agent architecture:** bespoke semantic layer to enrich data; isolated AI layer for text‑SQL‑text workflow.  
- **Smart AI routing:** automatically selects the fastest processing path for optimal speed.  
- **Latency:** sub‑second responses for common queries; < 30 seconds for complex analysis.  
- **Business‑ready outputs:** professional reports with data sources and confidence scoring.  
- **Continuous learning:** system improves accuracy through user interactions.

### Key Features

- **Real-Time Analysis:** Calculate ratios, compare companies, analyze trends instantly.  
- **Industry Intelligence:** Comprehensive sector benchmarking and competitive analysis.  
- **Strategic Decision Support:** Multi‑factor analysis for investment and risk assessment.  
- **Audit‑Ready Documentation:** Complete methodology transparency for compliance.  
- **50% Cost Savings:** Intelligent batch processing for large-scale analysis.  
- **Enterprise Security:** Multi‑layer validation ensures data safety and query protection.

---

## About the Authors

- **Julia Mickiewicz** — Client Executive for JPMC — https://www.linkedin.com/in/julia-mickiewicz-940317172/  
- **Srinidhi Ramanujam** — Senior Director for Data Science and AI — https://www.linkedin.com/in/srinidhiramanujam/  
- **Amir Tal** — Global Client Partner for JPMC — https://www.linkedin.com/in/amirtal/
