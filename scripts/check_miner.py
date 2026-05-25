#!/usr/bin/env python3
"""Watchdog: check if jay-miner is alive, restart if dead."""
import subprocess
import json
import sys
from datetime import datetime

def main():
    now = datetime.now().strftime("%H:%M:%S")
    
    # Check if miner process is running
    r = subprocess.run(["pgrep", "-f", "jay-miner.py"], capture_output=True, text=True)
    
    if r.returncode == 0:
        # Miner alive - check balance
        pids = r.stdout.strip().replace("\n", ", ")
        try:
            br = subprocess.run(
                ["curl", "-s", "--max-time", "10",
                 "https://api-jayn.winnode.xyz/cosmos/bank/v1beta1/balances/yjay1gas8jgqa7a6g6metcjvwqt9sug4399jrdrpgm0"],
                capture_output=True, text=True, timeout=15
            )
            data = json.loads(br.stdout)
            balance = next(
                (int(b["amount"])/1e6 for b in data.get("balances", []) if b.get("denom") == "ujay"),
                0
            )
            print(f"[{now}] ✅ Miner alive (PID: {pids}) | Balance: {balance:.6f} JAY")
        except Exception as e:
            print(f"[{now}] ✅ Miner alive (PID: {pids}) | Balance check failed: {e}")
    else:
        # Miner dead - restart
        print(f"[{now}] ⚠️ Miner DEAD! Restarting...")
        try:
            subprocess.run(["screen", "-X", "-S", "jay-miner", "quit"], capture_output=True, timeout=5)
        except:
            pass
        
        cmd = (
            'screen -dmS jay-miner bash -c '
            '\'cd /root/jay-miner && python3 jay-miner.py '
            '--wallet yjay1gas8jgqa7a6g6metcjvwqt9sug4399jrdrpgm0 '
            '--threads 8 --verbose --debug '
            '2>&1 | tee logs/miner-live.log; exec bash\''
        )
        subprocess.run(cmd, shell=True, timeout=10)
        
        # Verify it started
        import time
        time.sleep(3)
        r2 = subprocess.run(["pgrep", "-f", "jay-miner.py"], capture_output=True, text=True)
        if r2.returncode == 0:
            print(f"[{now}] ✅ Miner restarted! PID: {r2.stdout.strip()}")
        else:
            print(f"[{now}] ❌ Restart FAILED!")

if __name__ == "__main__":
    main()
