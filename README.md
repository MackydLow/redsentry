# RedSentry — Attack, Defend & AI Report Lab

A full-cycle penetration testing and defensive security lab built on two isolated UTM virtual
machines. Attack, detect, investigate, analyse, and report — with AI-assisted findings generation
via the Anthropic Claude API.

## Lab Architecture

UTM Host-Only Network (192.168.128.0/24) — Isolated from internet
|-- Kali Linux (Attacker / Blue Team / Analyst)
| Tools: Metasploit, Nmap, Burp Suite, Suricata, Autopsy, Ghidra, curl
'-- Metasploitable 2 (Target - Intentionally Vulnerable)
Deliberately vulnerable services: vsftpd, Samba, UnrealIRCd, DVWA


## Five Phases

### Phase 01 — Penetration Testing
Structured recon-to-root against two confirmed CVE backdoors and two confirmed OWASP Top 10 web
vulnerabilities, each with real evidence rather than version-banner speculation.

| Finding | Reference | Status | Severity (CVSS 3.1) |
|---------|-----------|--------|----------------------|
| vsftpd 2.3.4 Backdoor | CVE-2011-2523 | **Confirmed exploited** — root shell obtained | 9.8 Critical (combined finding) |
| UnrealIRCd 3.2.8.1 Backdoor | CVE-2010-2075 | **Confirmed exploited** — command shell obtained | 9.8 Critical (combined finding) |
| SQL Injection (DVWA) | OWASP A03:2021 | **Confirmed exploited** — full user table extracted | 8.6 High (combined web finding) |
| Command Injection (DVWA) | OWASP A03:2021 | **Confirmed exploited** — `/etc/passwd` read via injected `whoami`/`cat` | 8.6 High (combined web finding) |
| Samba usermap_script | CVE-2007-2447 | Version identified via anonymous SMB enumeration; **not exploited** | 5.3 Medium |

### Phase 02 — Network Defence
8 custom Suricata IDS rules authored, each mapped to a specific CVE or attack pattern. Rules were
live-fire tested against real attack traffic, not just syntax-validated.

| Rule | Detects | Result |
|------|---------|--------|
| 9000001/9000002 | vsftpd backdoor trigger + shell | Fired correctly during live exploitation |
| 9000004 | UnrealIRCd backdoor | Fired correctly during live exploitation |
| 9000005 | Nmap SYN scan (threshold-based) | Fired correctly during live scan |
| 9000007 | SQL injection (`OR 1=1` in URI) | Fired correctly against confirmed exploit |
| 9000008 | Command injection (`; whoami` in URI) | **Did not fire** — genuine detection gap identified (see below) |
| 9000003 | Samba usermap_script | Syntax-valid, not live-fire tested (Samba not exploited) |
| 9000006 | SSH brute force | Syntax-valid, not live-fire tested — blocked by a client/server crypto compatibility issue (see below) |

Alerts were also piped into a Filebeat -> Elasticsearch -> Kibana pipeline for SIEM-style querying.

### Phase 03 — Incident Response
Evidence collected from the compromised host via live shell access (no Meterpreter available —
session-upgrade attempts failed, so evidence was gathered and transcribed directly). A synthetic
disk image was built from the collected evidence and analysed in Autopsy, cross-referencing
keyword hits (`vsftpd`, `unrealircd`) with a live process ID recovered from the evidence, matching
the network-layer detection above. Memory forensics with Volatility 3 was attempted but not
possible in this environment (see Limitations) — string analysis of collected evidence was used
as a substitute, which surfaced a real finding: both `root` and `msfadmin` use weak `$1$`
(MD5-crypt) password hashes.

### Phase 04 — Malware Analysis
A benign, self-authored reverse-shell/beacon stub was analysed statically (Ghidra) and dynamically
(strace). Static analysis correctly predicted every runtime behaviour, including disproving one of
its own author's assumptions: hex-encoding an IP address in C source does **not** hide it from a
string-extraction tool, since the underlying bytes are still printable ASCII regardless of how
they're declared. Getting a working dynamic-analysis run required resolving a real cross-platform
compatibility chain — see Limitations & Lessons below.

### Phase 05 — AI-Assisted Reporting
A Python script sends structured evidence to the Claude API to draft professional finding
sections (CVSS 3.1 scoring, technical detail, remediation), which are then assembled into a full
report. The more significant part of this phase was the multi-round human review process that
followed generation — see Limitations & Lessons for specifics on what the AI got wrong and how it
was caught.

## Screenshots

### Reconnaissance & Exploitation
![Nmap full scan](docs/screenshots/01-nmap-full-scan.png)
![SMB enumeration](docs/screenshots/01-smb-enumeration.png)
![Nikto results](docs/screenshots/01-nikto-results.png)
![vsftpd root shell](docs/screenshots/01-exploit-vsftpd-root.png)
![UnrealIRCd backdoor shell](docs/screenshots/01-exploit-irc-backdoor.png)
![Post-exploitation evidence](docs/screenshots/01-post-exploit-shadow.png)
![All exploits successful](docs/screenshots/01-all-exploits-successful.png)
![DVWA command injection](docs/screenshots/01-dvwa-command-injection.png)

### Network Defence
![Suricata rules loaded](docs/screenshots/02-suricata-rules-loaded.png)
![Attack and detection side by side](docs/screenshots/02-suricata-detecting-attack.png)
![Alerts in Kibana](docs/screenshots/02-suricata-in-kibana.png)

### Digital Forensics
![Autopsy case open](docs/screenshots/03-autopsy-case-open.png)
![Autopsy keyword analysis](docs/screenshots/03-autopsy-keyword-analysis.png)
![Forensic timeline](docs/screenshots/03-forensic-timeline-1.png)

### Malware Analysis
![Malware sample compiled](docs/screenshots/04-malware-sample-compiled.png)
![Ghidra decompiled main](docs/screenshots/04-ghidra-main-decompiled.png)
![Ghidra connect trace](docs/screenshots/04-ghidra-connect-trace.png)
![Ghidra strings view](docs/screenshots/04-ghidra-strings-view.png)
![Confirmed dynamic execution and beacon capture](docs/screenshots/04-dynamic-analysis-strace-and-beacon.png)

### AI-Assisted Reporting
![API connection test](docs/screenshots/05-api-connection-test.png)
![Report generator running](docs/screenshots/05-report-generated.png)
![Report excerpt](docs/screenshots/05-report-excerpt2.png)

## Limitations & Lessons (the part that actually shows the work)

**Cross-architecture malware analysis.** The malware sample was compiled on the analysis
workstation (ARM64) but needed to run on the target (a 32-bit x86 Metasploitable2 image from
~2012). Four separate build attempts failed in sequence, each for a different real reason:
architecture mismatch (ARM64 vs x86), 64-bit vs the target's actual 32-bit kernel, a glibc version
gap of over a decade causing a missing-symbol failure, and finally a kernel ABI mismatch causing a
SIGSEGV even with static linking. The sample was ultimately compiled natively on the target using
its own toolchain, which resolved every compatibility layer at once. This is documented in full in
`phase04-malware/dynamic-analysis/`.
![Ghidra confirming the IP was findable despite hex-encoding](docs/screenshots/04-ghidra-strings-ip-found.png)

**A genuine IDS detection gap.** Suricata rule 9000008 (command injection detection) was written
using the `http.uri` sticky buffer. Live testing confirmed the underlying command injection
vulnerability was fully exploitable, but the rule never fired — root-cause analysis found DVWA's
vulnerable endpoint only accepts the payload via HTTP POST body, which a URI-scoped rule cannot
observe. This is a realistic, well-known class of IDS blind spot, not a rule-syntax bug, and is
documented with the diagnostic steps used to confirm it in `phase02-defence/`.
![Second page of the forensic timeline](docs/screenshots/03-forensic-timeline-2.png)

**Volatility 3 was not usable in this environment.** UTM on Apple Silicon exposes QEMU's monitor
interface exclusively via a Spice virtual channel rather than a TCP or Unix socket, which the
standard memory-dump technique depends on. This was confirmed by inspecting the live QEMU process
arguments rather than assumed. Manual string analysis of already-collected evidence was used as a
substitute and is documented in `phase03-forensics/memory-analysis/`.

**AI-generated reports require active auditing, not just spot-checking.** The reporting pipeline
went through several full review-and-correct cycles before the final version. Real issues caught
included: a `'ThinkingBlock' object has no attribute 'text'` runtime bug (Claude's API can return
a reasoning block before the text response, which the original code didn't account for); output
truncation from an initial token limit that was too low; a finding whose stated CVSS score
mathematically did not match its own CVSS vector string; a finding that scored Integrity/
Availability impact as High based on the malware's hypothetical future capability rather than its
demonstrated behaviour (corrected after recalculation, dropping the finding from Critical to
Medium); and, most significantly, an entire missing finding — the generator was never given the
confirmed exploitation evidence (Suricata detections plus Autopsy forensics) for vsftpd/UnrealIRCd,
so its first report described a fully-compromised host as merely "unconfirmed." None of these were
caught by the AI itself; all required comparing the AI's output against the underlying raw
evidence. Full notes in `phase05-reporting/prompts/prompt-engineering-notes.md`.

## Key Technical Skills Demonstrated

- Structured penetration testing methodology (recon -> enum -> exploit -> post-exploit)
- CVE research and exploit selection against specific software versions
- Custom IDS rule writing in Suricata (content matching, threshold detection, sticky buffers)
- Diagnosing IDS detection gaps by tracing rule scope against real attack delivery mechanisms
- Digital forensics with Autopsy, including working around tooling limitations
- Binary reverse engineering with Ghidra (static) and strace (dynamic)
- Cross-architecture/cross-toolchain build troubleshooting
- MITRE ATT&CK framework mapping
- Claude API integration, prompt engineering, and — critically — auditing AI output against
  source evidence rather than trusting it at face value
- Python automation of a full reporting pipeline

## MITRE ATT&CK Coverage

| Technique | ID | Phase |
|-----------|-----|-------|
| Exploit Public-Facing Application | T1190 | Exploitation (vsftpd, UnrealIRCd, DVWA) |
| Command and Scripting: Unix Shell | T1059.004 | Exploitation + Malware Analysis |
| Network Service Discovery | T1046 | Reconnaissance |
| Account Discovery: Local Account | T1087.001 | Enumeration (SMB) |
| Application Layer Protocol (C2) | T1071.001 | Malware Analysis |
| Time Based Sandbox Evasion | T1497.003 | Malware Analysis |

## Stack

Metasploit - Nmap - Burp Suite Community - Suricata - Autopsy - Ghidra - curl -
Metasploitable 2 - Claude API - Python 3 - UTM (Apple Silicon)
