Global Telecom Operator Industry News Collection and Structured Output

Objective
Collect and organize the latest global telecom operator industry developments, strategic partnerships, and major news events, with a strong emphasis on collaborations that demonstrate broad ecosystem alignment, industry consensus, and international cooperation trends.

Scope of Coverage

**Time Range**: {time_range}

Focus on, but do not limit coverage to:

* Mobile AI
* 5G-Advanced (5G-A)
* 6G
* Open RAN
* AI-Native Networks
* Cloud and Edge Computing
* Satellite Communications
* Network APIs
* Green Telecom / Energy Efficiency
* Autonomous Networks
* Telecom Infrastructure Innovation

Content Priorities

1. Multilateral Collaborations (Highest Priority)
   Prioritize news that reflects broad industry coordination and ecosystem collaboration, including:

* Enterprise-to-enterprise partnerships
* Industry–academia–research collaborations
* International organization initiatives
* Industry alliance developments
* Standards organization activities
* Cross-border ecosystem cooperation

Examples:

* GSMA joint initiatives
* ITU / 3GPP / TM Forum / O-RAN Alliance developments
* Multi-operator joint trials
* AI + Telecom ecosystem collaborations
* International 6G research programs

2. High-Impact Bilateral Collaborations (Secondary Priority)
   Include bilateral partnerships only if they demonstrate significant industry impact, technological importance, or strategic value, such as:

* Tier-1 operators partnering with major technology companies
* Telecom operators collaborating with AI companies
* Major commercial agreements or strategic investments
* Large-scale network deployment partnerships

Selection Criteria
Only include events that satisfy at least one of the following:

* Strategic significance for the global telecom industry
* Strong indication of emerging industry or ecosystem trends
* International or cross-regional collaboration involvement
* Strong relevance to AI, 5G-A, 6G, or next-generation communications
* Broad attention from industry organizations, major enterprises, or authoritative media
* Introduction of new business, cooperation, or ecosystem models

Output Requirements
The output MUST be a valid JSON array.

Each JSON object MUST contain the following fields:

* "date" — Publication date in YYYY-MM-DD format
* "source_url" — Original source link
* "title" — News headline
* "digest" — A concise 2–5 sentence summary describing:

  * the background of the event,
  * participating organizations,
  * relevant technologies,
  * and the broader industry significance

Output Rules

* All information MUST be based on real, verifiable news sources
* Prioritize official announcements, industry publications, international organizations, and authoritative technology media
* The digest MUST be concise, professional, and information-dense
* Avoid promotional or marketing language
* Avoid duplicate news entries
* Sort results in reverse chronological order (newest first)
* Output language MUST be English
* Do NOT output Markdown
* Do NOT include explanations, comments, or additional text
* Output ONLY the JSON array

Expected JSON Format
```json
[
    {{
        "date": "{example_date}",
        "source_url": "[https://example.com/news](https://example.com/news)",
        "title": "Example headline",
        "digest": "A concise summary describing the collaboration background, participating organizations, technology direction, and broader industry significance."
    }}
]
```