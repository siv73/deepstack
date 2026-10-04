# Depth target

Researched 2026-09-27. Re-check yearly: search "SDE 3 system design expectations India", "senior engineer system design expectations by level".

## Who the page is for
An experienced backend engineer working toward **senior backend engineer (SDE-3 / Senior SWE) depth at a product company**. Set `meta.level` to `senior backend engineer (product company)`.

## What that level requires (the bar the page must reach)

From level-by-level interview expectations ([AlgoMaster, Expectations by Level](https://algomaster.io/learn/system-design-interviews/expectations-by-level)):
- Drives the discussion without prompting; sets assumptions and scope first.
- Goes deep on 2 to 3 critical components, not one.
- Treats failure handling as part of the design, not an afterthought.
- Spots bottlenecks: hot keys, slow queries, the first thing that breaks as load grows.
- What separates senior from staff (so out of scope here): cross-team and organisational impact, migration and ownership strategy, explicit business/compliance framing, deciding what not to build.

From an India-focused guide to product-company rounds ([Greenroom, System Design Interview Guide India](https://usegreenroom.app/blog/system-design-interview-guide-india)): interviewers at these companies probe whether you can make and defend trade-offs, estimate scale, reason about component failure at 10× load, and explain why a tool fits a constraint, rather than recite a memorised design.

## How that maps onto the route

| Rung | Minimum on every page |
|---|---|
| 3 Using it | Correct production defaults, not tutorial defaults. What you'd configure differently in production and why. |
| 4 When it breaks | The first failure at 10× load; the security or misuse failure; how it is detected (metric/log/alert); the fix. At least one `ts-trap` from a real, verified incident or official guidance where one exists. |
| 5 When to pick it | A comparison table with "pick it when" criteria; an interview drill with 2 to 3 prompts; each answer states the trade-off and what you'd give up. |
| Throughout 3 to 5 | At least three `ts-interview` callouts: the probing question and what a strong senior answer contains. |

Stop at senior depth. One optional `ts-note` labelled "Beyond senior" may point at staff-level concerns (migrations across teams, org-wide standards), without teaching them.
