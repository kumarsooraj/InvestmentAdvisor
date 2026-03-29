#!/usr/bin/env python3
"""Run this once to securely save your Anthropic API key to .env"""
import re, os

print("=" * 50)
print("Investment Advisor — API Key Setup")
print("=" * 50)
print("\nGet your key from: https://console.anthropic.com/")
print("Make sure it shows as Active (not Revoked)\n")

key = input("Paste your Anthropic API key here: ").strip()

if not key.startswith("sk-ant-"):
    print("That doesn't look like a valid Anthropic key (should start with sk-ant-)")
    exit(1)

env_path = os.path.join(os.path.dirname(__file__), ".env")
with open(env_path) as f:
    content = f.read()

content = re.sub(r"ANTHROPIC_API_KEY=.*", f"ANTHROPIC_API_KEY={key}", content)

with open(env_path, "w") as f:
    f.write(content)

print(f"\n✓ Key saved to .env (length: {len(key)} chars)")
print("✓ This file is gitignored — your key stays private")
print("\nNow run:  python main.py run")
