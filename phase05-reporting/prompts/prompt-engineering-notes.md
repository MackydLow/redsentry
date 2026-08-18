# AI Reporting — Prompt Engineering Notes

The most important design decisions in the report generator:

1. SEPARATION OF SYSTEM AND USER PROMPTS
   The system prompt defines Claude's role ("professional pentester with 10 years experience").
   The user prompt provides the task and data. Keeping these separate makes the prompt more
   reliable — the role context applies to every API call consistently.

2. STRUCTURED OUTPUT FORMAT
   The user prompt specifies the exact output format with section headers and a table structure.
   Without this, the AI produces narrative prose that's hard to parse programmatically.
   With it, the output is consistent enough to assemble into a report automatically.

3. TOKEN MANAGEMENT
   Raw tool output is truncated at 8000 characters per file. Nmap output for a full scan
   can be 50,000+ characters. Truncating keeps API costs low and focuses the model on
   the most relevant data. Individual finding generation was also increased from 2000 to
   8000 max_tokens during this project after early runs truncated mid-finding.

4. HUMAN VALIDATION STEP
   The script adds a note that all AI-generated content must be reviewed. CVSS scores
   from AI should always be cross-referenced against the CVSS 3.1 calculator and NVD.
   In practice, this project's review process caught several real issues: a CVSS score
   that didn't match its own vector string (mathematically inconsistent), a finding that
   scored impact based on hypothetical future capability rather than demonstrated
   behaviour (corrected from Critical to Medium after recalculation), a missing finding
   entirely (confirmed exploitation evidence that existed but wasn't fed to the generator
   in the initial run), and a factual date error (a backdoor's compromise window stated
   with month order reversed). None of these were caught by the AI itself — all required
   manual review against the underlying evidence.

Cost for this project: approximately £1-3 total in API credits across all generation runs.


## Supporting Screenshots

See `docs/screenshots/05-api-connection-test.png`, `05-report-generated.png`,
`05-report-excerpt2.png`, and `05-report-excerpt3.png` for the generator running
and sample output at various stages of the review-and-correction process
described above.
