#!/usr/bin/env python3
"""
RedSentry AI Report Generator
Feeds raw pentest tool output into Claude API to generate
professional penetration testing report sections.
"""

import anthropic
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime

# Colour output
class Colours:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def log(msg, colour=None):
    if colour:
        print(f"{colour}{msg}{Colours.RESET}")
    else:
        print(msg)

def read_file_safe(filepath):
    """Read a file, return empty string if not found."""
    try:
        with open(filepath, 'r', errors='replace') as f:
            content = f.read()
        return content[:8000]  # Limit to 8000 chars per file to manage token cost
    except FileNotFoundError:
        return f"[File not found: {filepath}]"

def generate_finding(client, finding_type, raw_data, phase):
    """
    Call Claude API to generate a professional finding section.
    This is the core prompt engineering function.
    """
    
    # System prompt: defines Claude's role and output format
    system_prompt = """You are a professional penetration testing report writer with 10 years of experience
writing reports for major security consultancies. Your reports are clear, accurate, and suitable for 
both technical security teams and non-technical executives.

You must always:
- Assign accurate CVSS 3.1 scores based on the evidence provided
- Use precise technical language in the Technical Detail section
- Use plain English in the Executive Summary (suitable for a CEO)
- Provide specific, actionable remediation steps
- Map findings to MITRE ATT&CK techniques where applicable
- Never invent vulnerabilities not evidenced in the data provided
- If the evidence does not confirm successful exploitation, clearly state
  that the finding is based on service/version identification or scanner
  output only, and reflect this in a lower CVSS score and in the
  Executive Summary — do not describe untested vulnerabilities as
  confirmed or exploited

Output ONLY the formatted finding — no preamble, no commentary."""

    # User prompt: structured request with the raw data
    user_prompt = f"""Analyse the following {finding_type} data from a penetration test and generate 
a professional finding section.

RAW TOOL OUTPUT:
{raw_data}

Generate a finding section in this EXACT format:

---
## Finding: [Descriptive title of the vulnerability]

**CVSS Score:** [X.X] ([Critical/High/Medium/Low])
**CVSS Vector:** [Full CVSS 3.1 vector string, MUST start with "CVSS:3.1/" prefix, e.g. CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N]
**MITRE ATT&CK:** [Technique ID] — [Technique Name]

### Executive Summary
[2-3 sentences explaining the vulnerability and its business impact in plain English. 
Avoid technical jargon. Explain what a real attacker could do with this.]

### Technical Detail
[3-5 paragraphs of technical explanation including:
- What the vulnerability is and why it exists
- How it was discovered (tools/methods used)
- The attack chain from initial access to impact
- Why this is exploitable in this specific configuration]

### Evidence
[Specific evidence from the tool output above — exact commands run and key output snippets.
Format as a code block where appropriate.]

### CVSS Breakdown
| Metric | Value | Rationale |
|--------|-------|-----------|
| Attack Vector | [value] | [reason] |
| Attack Complexity | [value] | [reason] |
| Privileges Required | [value] | [reason] |
| User Interaction | [value] | [reason] |
| Scope | [value] | [reason] |
| Confidentiality | [value] | [reason] |
| Integrity | [value] | [reason] |
| Availability | [value] | [reason] |

### Remediation
[Numbered list of specific remediation steps, ordered by priority.
Include specific configuration changes, version updates, or architectural improvements.
Be concrete — say exactly what to change, not just "patch the system".]

### References
[CVE numbers, vendor advisories, NIST entries relevant to this finding]
---
"""

    log(f"\n  Calling Claude API for: {finding_type}...", Colours.BLUE)
    
    try:
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=8000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        text_blocks = [block.text for block in response.content if block.type == 'text']
        if not text_blocks:
            raise ValueError(f"No text block in response (stop_reason={response.stop_reason}, blocks={[b.type for b in response.content]})")
        return text_blocks[0]
        
    except Exception as e:
        log(f"  API error: {e}", Colours.RED)
        return f"[Error generating finding: {e}]"


def generate_executive_summary(client, all_findings_summary):
    """Generate the overall executive summary for the report."""
    
    prompt = f"""You are a senior penetration testing consultant.
Based on the following findings summary, write a 4-paragraph executive summary for a penetration test report.

IMPORTANT CONTEXT: The "Malware Analysis" finding refers to a benign sample that the
assessment team authored and compiled themselves specifically to test malware-analysis
capability (static and dynamic reverse engineering). It was NOT discovered already
present in the environment, and does not indicate an existing compromise. Do not describe
it as "already embedded," "already present," or similar language implying a live threat
was found. Describe it accurately as a controlled analysis exercise that validated the
team's malware analysis tooling and methodology.

Findings: {all_findings_summary}

The executive summary should:
1. Paragraph 1: What was tested, when, and the overall risk level
2. Paragraph 2: The most critical findings in plain English (no jargon)
3. Paragraph 3: The root cause themes across all findings (e.g. patch management failure, weak credentials)
4. Paragraph 4: The recommended priority order for remediation

Write it for a CISO or CTO audience. Maximum 400 words total. Do not use bullet points."""

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}]
    )
    text_blocks = [block.text for block in response.content if block.type == 'text']
    if not text_blocks:
        raise ValueError(f"No text block in response (stop_reason={response.stop_reason}, blocks={[b.type for b in response.content]})")
    text = text_blocks[0].strip()
    text = re.sub(r'^\s*#+\s*Executive Summary\s*\n+', '', text, flags=re.IGNORECASE)
    return text


def assemble_report(findings, exec_summary, output_path):
    """Assemble all sections into the final report."""
    
    report = f"""# RedSentry Penetration Test Report
## Target: Metasploitable 2 | Classification: CONFIDENTIAL
## Date: {datetime.now().strftime('%Y-%m-%d')} | Generated with AI-assisted reporting

## Scope & Engagement Details

**Scope:** 192.168.128.8 (Metasploitable2), including all TCP/UDP services identified during reconnaissance
**Engagement Type:** Authorized internal penetration test — isolated lab environment
**Distribution:** Restricted — for review by the assessment author and authorized reviewers only
**Limitations:** This report reflects a point-in-time assessment. Findings marked "unconfirmed" or "not live-tested" represent identified risk based on version/service fingerprinting, not demonstrated exploitation, and should be validated before being treated as confirmed vulnerabilities.

---

## Executive Summary

{exec_summary}

---

## Findings Summary

| # | Finding | Severity | CVSS |
|---|---------|----------|------|
"""
    for i, (name, _, severity, cvss) in enumerate(findings, 1):
        report += f"| {i} | {name} | {severity} | {cvss} |\n"
    
    report += "\n---\n\n## Detailed Findings\n\n"
    
    for _, content, _, _ in findings:
        report += content.strip() + "\n\n"
    
    report += f"""
## Appendix A — Tools Used

| Tool | Purpose | Phase |
|------|---------|-------|
| Nmap 7.x | Port scanning and service detection | Reconnaissance |
| Metasploit Framework | Exploitation framework | Exploitation |
| Burp Suite Community | Web proxy and scanner | Web Testing |
| enum4linux | SMB enumeration | Enumeration |
| Nikto | Web server scanner | Web Testing |
| Suricata | Network IDS / detection | Defence |
| Autopsy | Disk forensics | Incident Response |
| Volatility 3 | Memory forensics (attempted; substituted with manual string analysis — see limitations) | Incident Response |
| Ghidra | Static binary analysis | Malware Analysis |
| Claude API (claude-sonnet-5) | AI report generation | Reporting |

## Appendix B — Methodology

This assessment followed a structured penetration testing methodology:

1. **Reconnaissance** — Passive and active information gathering using Nmap
2. **Enumeration** — Service-specific interrogation to identify credentials and vulnerabilities  
3. **Exploitation** — Controlled exploitation of identified vulnerabilities
4. **Post-Exploitation** — Assessment of impact following successful compromise
5. **Defence Correlation** — Detection rule writing and alert validation
6. **Forensic Analysis** — Evidence collection and timeline reconstruction
7. **Malware Analysis** — Static and dynamic analysis of attack tools
8. **Reporting** — AI-assisted generation of structured findings

## Appendix C — AI Reporting Methodology

This report was generated using a hybrid human-AI workflow:

1. Raw tool output was collected in structured text files during each phase
2. Outputs were fed to Claude (claude-sonnet-5) via the Anthropic API with structured prompts
3. Claude generated initial finding sections including CVSS scores and remediation advice
4. All AI-generated content was reviewed and validated against the actual evidence
5. CVSS scores were cross-referenced against the NVD database for accuracy

This workflow mirrors commercial tools like PlexTrac and AttackIQ that use AI to accelerate finding documentation. The value is not in replacing analyst judgment — it's in reducing the time spent on formatting and boilerplate writing, leaving more time for analysis.

---

*Report generated by RedSentry AI Report Generator | github.com/MackydLow/redsentry*
"""
    
    with open(output_path, 'w') as f:
        f.write(report)
    
    log(f"\n✅ Report saved to: {output_path}", Colours.GREEN)
    return report


def main():
    log("\n" + "="*60, Colours.BOLD)
    log("  RedSentry AI Penetration Test Report Generator", Colours.BOLD)
    log("="*60 + "\n", Colours.BOLD)
    
    # Initialise client
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        log("ERROR: ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY='sk-ant-...'", Colours.RED)
        sys.exit(1)
    
    client = anthropic.Anthropic(api_key=api_key)
    log("✅ Claude API connected", Colours.GREEN)
    
    base_dir = Path.home() / 'redsentry'
    
    # Define what to analyse and generate
    analysis_tasks = [
        {
            'type': 'SMB Enumeration — Samba 3.0.20',
            'file': '02-enumeration/smb-enum.txt',
            'focus': 'Focus on Samba version and CVE-2007-2447 usermap_script exploit'
        },
        {
            'type': 'Web Application — SQL Injection and Command Injection',
            'file': '05-web/web-notes.txt',
            'focus': 'Focus on OWASP Top 10 findings: SQLi and command injection in DVWA. Note that this engagement did not include confirmed live exploitation of these specific vulnerabilities — reflect this accurately.'
        },
        {
            'type': 'Malware Analysis — Reverse Shell Stub (Static + Dynamic)',
            'file': '07-malware/static-analysis-notes.md',
            'file2': '07-malware/dynamic-analysis-notes.md',
            'focus': 'Focus on MITRE T1059.004, the evasion techniques identified in static analysis, AND the dynamic analysis results — the sample WAS successfully executed under strace and its beacon WAS received by a listener, confirming every static prediction at runtime. Do not describe this as unexecuted or unconfirmed.'
        },
        {
            'type': 'Confirmed Exploitation — vsftpd 2.3.4 and UnrealIRCd Backdoors',
            'file': '08-reports/phase02-suricata-alerts.txt',
            'file2': '08-reports/phase03-autopsy-analysis.txt',
            'focus': 'This finding covers CONFIRMED, fully exploited compromises — not version detection. vsftpd 2.3.4 (CVE-2011-2523) was exploited via Metasploit, root shell obtained, and detected in real time by Suricata rules 9000001/9000002 (both confirmed firing in fast.log). UnrealIRCd 3.2.8.1 (CVE-2010-2075) was also exploited via Metasploit (bind_perl payload), giving a working command shell used for subsequent evidence collection, and independently corroborated via Autopsy disk forensics finding the unrealircd process actively running (PID 4749) at time of evidence capture. Score this as CONFIRMED exploitation with demonstrated impact, not a theoretical/unconfirmed finding.'
        },
    ]
    
    findings = []
    
    for task in analysis_tasks:
        log(f"\n📋 Analysing: {task['type']}", Colours.YELLOW)
        
        # Read the raw data
        raw_data = read_file_safe(base_dir / task['file'])
        if 'file2' in task:
            raw_data += "\n\n=== ADDITIONAL FILE ===\n\n" + read_file_safe(base_dir / task['file2'])
        
        # Add focus instruction to raw data
        input_data = f"FOCUS: {task['focus']}\n\nRAW DATA:\n{raw_data}"
        
        # Generate the finding
        finding_content = generate_finding(client, task['type'], input_data, 'pentest')
        
        # Extract the actual severity/CVSS Claude assigned, from the text itself
        match = re.search(r'\*\*CVSS Score:\*\*\s*([\d.]+)\s*\(([A-Za-z]+)\)', finding_content)
        if match:
            cvss = match.group(1)
            severity = match.group(2)
        else:
            severity = "Unknown"
            cvss = "N/A"
        
       # Extract the actual finding title Claude generated, for the summary table
        title_match = re.search(r'##\s*Finding:\s*(.+)', finding_content)
        display_name = title_match.group(1).strip() if title_match else task['type']

        findings.append((display_name, finding_content, severity, cvss))
        log(f"  ✅ Finding generated ({severity}, CVSS {cvss})", Colours.GREEN)

    # Sort findings by CVSS score, highest first
    def sort_key(f):
        try:
            return float(f[3])
        except (ValueError, TypeError):
            return 0.0
    findings.sort(key=sort_key, reverse=True)

    # Generate executive summary
    log("\n📋 Generating executive summary...", Colours.YELLOW)
    summary_text = "\n".join([f"- {name} ({sev}, CVSS {cvss})" for name, _, sev, cvss in findings])
    exec_summary = generate_executive_summary(client, summary_text)
    log("  ✅ Executive summary generated", Colours.GREEN)
    
    # Assemble and save report
    log("\n📋 Assembling final report...", Colours.YELLOW)
    output_path = base_dir / '08-reports' / f'redsentry-report-{datetime.now().strftime("%Y%m%d")}.md'
    assemble_report(findings, exec_summary, output_path)
    
    # Save for GitHub
    github_copy = base_dir / '08-reports' / 'PENTEST-REPORT.md'
    assemble_report(findings, exec_summary, github_copy)
    
    log("\n" + "="*60, Colours.BOLD)
    log("  Report generation complete!", Colours.BOLD)
    log(f"  Report saved to: {output_path}", Colours.BOLD)
    log("="*60 + "\n", Colours.BOLD)


if __name__ == "__main__":
    main()
