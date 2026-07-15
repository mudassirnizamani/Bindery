#!/usr/bin/env python3
"""
Helper script to install hutrans with proper numpy headers
"""
import os
import sys
import subprocess
import numpy

def main():
    try:
        # Get numpy include directory
        numpy_include = numpy.get_include()
        print(f"NumPy include directory: {numpy_include}")
        
        # Set environment variables for compilation
        env = os.environ.copy()
        env['CFLAGS'] = f"-I{numpy_include}"
        env['CPPFLAGS'] = f"-I{numpy_include}"
        
        # Install hutrans with proper headers
        cmd = [
            sys.executable, '-m', 'pip', 'install',
            '--no-build-isolation',
            'git+https://github.com/ltrc/python-hutrans.git'
        ]
        
        print(f"Running: {' '.join(cmd)}")
        print(f"CFLAGS: {env.get('CFLAGS')}")
        
        result = subprocess.run(cmd, env=env, check=True)
        print("✅ hutrans installed successfully!")
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install hutrans: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 