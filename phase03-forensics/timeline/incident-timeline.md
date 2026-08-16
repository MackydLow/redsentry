# Incident Timeline — RedSentry Case RS-2026-001

## System: Metasploitable 2 | IP: 192.168.128.8
## Analyst: Mack | Date: 2026-07-26

---

## Timeline of Compromise

| Time | Event | Source | Evidence |
|------|-------|--------|----------|
| T+0:00 | Nmap SYN scan (200 ports) from Kali (192.168.128.7) | Suricata Rule 9000005 | fast.log — REDSENTRY Nmap SYN Scan Detected |
| T+0:02 | vsftpd 2.3.4 backdoor trigger — USER containing ":)" sent to port 21 | Suricata Rule 9000001 | fast.log — REDSENTRY vsftpd 2.3.4 Backdoor Trigger |
| T+0:02 | Backdoor shell connection opened on port 6200 | Suricata Rule 9000002 | fast.log — REDSENTRY vsftpd Backdoor Shell |
| T+0:10 | UnrealIRCd backdoor exploited via crafted IRC command (port 6667) | Metasploit exploit output | msf console log — "Backdoor has been spawned" |
| T+0:10 | Command shell session established (bind_perl payload, port 4444) | Metasploit sessions -l | session 1 confirmed active |
| T+0:12 | Evidence collected from compromised host: /etc/passwd, /etc/shadow, auth.log, process list, network connections, cron | Manual shell access | 06-forensics/*.txt |
| T+0:20 | Disk image built from collected evidence, imported into Autopsy | Autopsy case RedSentry-Incident-001 | evidence.img, MD5 80BE5924742E412B8AD6A13DEBC192AB |
| T+0:22 | Keyword search confirms unrealircd running as live process (PID 4749) | Autopsy keyword search | fragment 8734/8735 |

## Impact Assessment

- Data accessed: /etc/passwd, /etc/shadow (all local user credentials — both root and msfadmin use weak $1$/MD5-crypt hashes)
- Access level: Root (confirmed via `whoami`/`id` in shell session)
- Services exploited: FTP (vsftpd 2.3.4 backdoor), IRC (UnrealIRCd 3.2.8.1 backdoor)
- Services scanned but not exploited in this engagement: SSH, HTTP, SMB (rules 9000003, 9000006, 9000007, 9000008 written and loaded but not live-tested against real traffic — see Phase 02 notes)
- Persistence mechanisms found: None identified (crontab -l and /etc/cron* checked — no attacker-installed persistence found)
- Notable anomaly: root and msfadmin .bash_history both symlinked to /dev/null (pre-existing image characteristic, not attacker-installed)

## Indicators of Compromise (IOCs)

- Source IP of attacker: 192.168.128.7 (Kali)
- Target IP: 192.168.128.8 (Metasploitable)
- Port 6200 connection from target (vsftpd backdoor shell)
- FTP USER command containing ":)" string
- IRC traffic on port 6667 associated with UnrealIRCd backdoor exploitation
- Process unrealircd running as PID 4749 at time of evidence capture

## Root Cause

Two confirmed unpatched CVEs (CVE-2011-2523 — vsftpd 2.3.4 backdoor; UnrealIRCd 3.2.8.1 backdoor, CVE-2010-2075) combined with no network segmentation, no IDS, and no monitoring on the target host. Both exploits were successfully detected in real time by custom Suricata rules once deployed, and corroborated after the fact via disk forensics (Autopsy). A genuine memory capture (Volatility 3) was attempted but not obtainable due to UTM/QEMU exposing its monitor interface via Spice rather than a standard socket — documented as a limitation for future work.
