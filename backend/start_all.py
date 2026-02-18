#!/usr/bin/env python3
"""
🚀 Start All Services: Scheduler + Pipeline Workers
═══════════════════════════════════════════════════════════════
يشغّل الـ scheduler والـ pipeline workers في نفس الوقت

Usage:
    python start_all.py
═══════════════════════════════════════════════════════════════
"""

import subprocess
import sys
import os
import signal
import time

# ─── ألوان للـ terminal ───────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def print_header():
    print(f"\n{BOLD}{'═' * 70}{RESET}")
    print(f"{BOLD}  🚀 Starting All Services{RESET}")
    print(f"{BOLD}{'═' * 70}{RESET}\n")


def main():
    print_header()

    processes = []

    try:
        # 1️⃣ شغّل الـ Scheduler
        print(f"{BLUE}1️⃣  Starting Scheduler...{RESET}")
        scheduler_proc = subprocess.Popen(
            [sys.executable, 'scheduler.py'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(('Scheduler', scheduler_proc))
        print(f"{GREEN}   ✅ Scheduler started (PID: {scheduler_proc.pid}){RESET}\n")

        time.sleep(2)

        # 2️⃣ شغّل الـ Pipeline Workers
        print(f"{BLUE}2️⃣  Starting Pipeline Workers...{RESET}")
        workers_proc = subprocess.Popen(
            [sys.executable, 'pipeline_queue_workers.py'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(('Pipeline Workers', workers_proc))
        print(f"{GREEN}   ✅ Pipeline Workers started (PID: {workers_proc.pid}){RESET}\n")

        print(f"{BOLD}{'═' * 70}{RESET}")
        print(f"{GREEN}{BOLD}✅ All services running!{RESET}")
        print(f"{BOLD}{'═' * 70}{RESET}\n")
        print(f"{YELLOW}Press Ctrl+C to stop all services{RESET}\n")

        # اقرأ الـ output من كل process
        while True:
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"{RED}❌ {name} stopped unexpectedly!{RESET}")
                    sys.exit(1)
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutting down all services...{RESET}\n")

        for name, proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                print(f"{GREEN}✅ {name} stopped{RESET}")
            except subprocess.TimeoutExpired:
                proc.kill()
                print(f"{YELLOW}⚠️  {name} force killed{RESET}")
            except Exception as e:
                print(f"{RED}❌ Error stopping {name}: {e}{RESET}")

        print(f"\n{GREEN}All services stopped{RESET}\n")
        sys.exit(0)

    except Exception as e:
        print(f"{RED}❌ Error: {e}{RESET}")
        for name, proc in processes:
            try:
                proc.kill()
            except:
                pass
        sys.exit(1)


if __name__ == '__main__':
    main()
