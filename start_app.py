#!/usr/bin/env python3
"""
Smart startup script for the Twitter Monitor app with port conflict detection
"""
import os
import sys
import socket
import subprocess
import signal
import time

def is_port_in_use(port):
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('', port))
            return False
        except:
            return True

def get_processes_on_port(port):
    """Get process IDs using a specific port"""
    try:
        result = subprocess.run(['lsof', '-ti', f':{port}'], 
                              capture_output=True, text=True)
        if result.returncode == 0 and result.stdout:
            return [int(pid) for pid in result.stdout.strip().split('\n')]
    except:
        pass
    return []

def kill_processes_on_port(port):
    """Kill processes using a specific port"""
    pids = get_processes_on_port(port)
    if pids:
        print(f"Found {len(pids)} process(es) using port {port}: {pids}")
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Killed process {pid}")
            except:
                print(f"Failed to kill process {pid}")
        time.sleep(2)  # Give processes time to shut down
        return True
    return False

def find_available_port(start_port=5001, max_attempts=10):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(port):
            return port
    return None

def main():
    """Main startup function"""
    default_port = 5001
    
    # Check if default port is in use
    if is_port_in_use(default_port):
        print(f"Port {default_port} is already in use.")
        
        # Ask user what to do
        print("\nOptions:")
        print("1. Kill existing processes and use port 5001")
        print("2. Find and use an alternative port")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == '1':
            if kill_processes_on_port(default_port):
                print(f"Cleared port {default_port}")
                port = default_port
            else:
                print("Failed to clear port, finding alternative...")
                port = find_available_port(default_port + 1)
        elif choice == '2':
            port = find_available_port(default_port + 1)
        else:
            print("Exiting...")
            sys.exit(0)
    else:
        port = default_port
    
    if port is None:
        print("No available ports found. Please free up a port and try again.")
        sys.exit(1)
    
    # Set the port in environment if different from default
    if port != default_port:
        os.environ['PORT'] = str(port)
        print(f"\nUsing port {port} instead of default {default_port}")
    
    print(f"\nStarting Twitter Monitor on port {port}...")
    print(f"Access the application at: http://localhost:{port}")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Start the Flask app
    try:
        subprocess.run([sys.executable, 'app.py'])
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
        sys.exit(0)

if __name__ == "__main__":
    main()