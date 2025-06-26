#!/usr/bin/env python3

import os
import subprocess
import sys

# Clear problematic environment variables
problematic_vars = []
for key, value in os.environ.items():
    if '#' in value:
        problematic_vars.append(key)

for var in problematic_vars:
    del os.environ[var]
    print(f"Cleared {var}")

# Load environment variables properly
env_file = '.env.development'
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove any inline comments
                if '#' in value:
                    value = value.split('#')[0].strip()
                value = value.strip('"\'')
                os.environ[key] = value
                print(f"Set {key}={value}")

# Start the application
if __name__ == "__main__":
    print("Starting application...")
    subprocess.run([sys.executable, 'app.py']) 