#!/usr/bin/env python3
"""
================================================================================
APIC fvCEp (Client Endpoint) Data Extraction Tool
================================================================================
Purpose: Query Cisco APIC REST API for fvCEp (Client Endpoint) class data 
         and export endpoint information including EPG, MAC, IP, Interface, 
         and Encapsulation data to CSV
Author: Shafie A
Date: 2026-05-11

Requirements:
  - Python 3.7+
  - requests library (install with: pip install requests)

Usage:
  1. Place your .env file in the same directory as this script (optional)
  2. Run: python apic_fvcep_extractor.py
  3. Provide credentials when prompted (or they'll be read from .env)
  4. CSV file will be created in the same directory

================================================================================
"""

import os
import json
import csv
import sys
import warnings
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

try:
    import requests
    from requests.auth import HTTPBasicAuth
    from urllib3.exceptions import InsecureRequestWarning
except ImportError:
    print("ERROR: 'requests' library not found!")
    print("Install it with: pip install requests")
    sys.exit(1)

# Suppress SSL warnings for lab environments
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class APICClient:
    """Client for Cisco APIC REST API"""
    
    def __init__(self, apic_url, username, password, verify_ssl=False, timeout=30):
        """
        Initialize APIC Client
        
        Args:
            apic_url: APIC controller URL (e.g., https://apic.example.com)
            username: APIC username
            password: APIC password
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
        """
        self.apic_url = apic_url.rstrip('/')
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.token = None
        self.session_id = None
        
    def login(self):
        """
        Authenticate to APIC and get session token
        
        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            url = urljoin(self.apic_url, '/api/aaaLogin.json')
            payload = {
                "aaaUser": {
                    "attributes": {
                        "name": self.username,
                        "pwd": self.password
                    }
                }
            }
            
            print(f"[*] Authenticating to APIC: {self.apic_url}")
            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract token and session ID
            if 'imdata' in data and len(data['imdata']) > 0:
                login_attr = data['imdata'][0]['aaaLogin']['attributes']
                self.token = login_attr.get('token')
                self.session_id = login_attr.get('sessionId')
                
                if self.token:
                    print(f"[✓] Successfully authenticated!")
                    print(f"    Session ID: {self.session_id}")
                    return True
            
            print("[✗] Login failed: No token in response")
            return False
            
        except requests.exceptions.SSLError as e:
            print(f"[✗] SSL Error: {str(e)}")
            print("    Try setting verify_ssl=False or updating certificates")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"[✗] Connection Error: {str(e)}")
            print(f"    Cannot reach {self.apic_url}")
            return False
        except Exception as e:
            print(f"[✗] Login failed: {str(e)}")
            return False
    
    def query_fvcep(self, page=0, page_size=1000):
        """
        Query fvCEp (Client Endpoint) class from APIC with specified parameters
        Retrieves endpoint data including MAC address, IP, Interface, and Encapsulation
        
        Args:
            page: Page number (0-indexed)
            page_size: Number of records per page
            
        Returns:
            dict: API response JSON or None if failed
        """
        try:
            url = urljoin(self.apic_url, '/api/node/class/fvCEp.json')
            
            # Build query parameters as specified
            params = {
                "query-target-filter": 'not(wcard(fvCEp.dn,"__ui_"))',
                "rsp-subtree": "children",
                "order-by": "fvCEp.mac|asc",
                "page": page,
                "page-size": 1000
            }
            
            # Set up cookie with token
            cookies = {"APIC-cookie": self.token}
            
            print(f"[*] Querying fvCEp data (page {page}, size {page_size})...")
            response = self.session.get(
                url,
                params=params,
                cookies=cookies,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            result = response.json()
            return result
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                print("[✗] Authentication error - token may have expired")
            else:
                print(f"[✗] HTTP Error {response.status_code}")
            return None
        except Exception as e:
            print(f"[✗] Query failed: {str(e)}")
            return None
    
    def fetch_all_pages(self, page_size=1000):
        """
        Fetch all pages of fvCEp data
        
        Args:
            page_size: Number of records per page
            
        Returns:
            list: All fvCEp records from all pages
        """
        all_data = []
        page = 0
        max_pages = 10000  # Safety limit to prevent infinite loops
        
        while page < max_pages:
            print(f"\n[*] Fetching page {page}...")
            result = self.query_fvcep(page=page, page_size=page_size)
            
            if not result:
                print(f"[✗] Query returned no result")
                break
            
            imdata = result.get('imdata', [])
            if not imdata:
                print(f"[✓] No more data available")
                if page == 0:
                    print("[!] No records found matching the query criteria")
                break
            
            all_data.extend(imdata)
            total_count = len(all_data)
            print(f"[✓] Page {page}: {len(imdata)} records (Total: {total_count})")
            
            # Check if this is the last page
            if len(imdata) < page_size:
                print(f"[✓] Reached last page")
                break
            
            page += 1
        
        print(f"\n[✓] Data fetch complete: {len(all_data)} total records retrieved")
        return all_data
    
    def parse_endpoint_data(self, data):
        """
        Parse fvCEp endpoint data and extract relevant fields
        
        Args:
            data: List of fvCEp records from API
            
        Returns:
            list: List of parsed endpoint records with EPG, MAC, IP, Interface, Encap
        """
        endpoints = []
        
        for item in data:
            if 'fvCEp' in item:
                fv_cep = item['fvCEp']
                attributes = fv_cep.get('attributes', {})
                
                # Extract main endpoint attributes
                endpoint = {
                    'MAC Address': attributes.get('mac', ''),
                    'DN (Distinguished Name)': attributes.get('dn', ''),
                    'Encapsulation': attributes.get('encap', ''),
                    'Interface': attributes.get('ifId', ''),
                    'Status': attributes.get('status', ''),
                    'Last Modified': attributes.get('modTs', ''),
                    'Name': attributes.get('name', ''),
                    'IP Address': '',
                    'EPG': '',
                }
                
                # Extract EPG from DN path
                # DN format: uni/tn-{tenant}/ap-{app}/epg-{epg}/cep-mac-{mac}
                dn = attributes.get('dn', '')
                try:
                    if '/epg-' in dn:
                        epg_part = dn.split('/epg-')[1].split('/')[0]
                        endpoint['EPG'] = epg_part
                    if '/tn-' in dn:
                        tenant_part = dn.split('/tn-')[1].split('/')[0]
                        endpoint['Tenant'] = tenant_part
                except:
                    pass
                
                # Parse children for IP and Interface information
                children = fv_cep.get('children', [])
                interfaces = []
                
                for child in children:
                    # Parse fvIp (IP Address info)
                    if 'fvIp' in child:
                        ip_attrs = child['fvIp'].get('attributes', {})
                        ip_addr = ip_attrs.get('addr', '')
                        if ip_addr:
                            endpoint['IP Address'] = ip_addr
                    
                    # Parse fvRsCEpToPathEp (Interface/Path info)
                    elif 'fvRsCEpToPathEp' in child:
                        path_attrs = child['fvRsCEpToPathEp'].get('attributes', {})
                        path_dn = path_attrs.get('tDn', '')
                        if path_dn:
                            interfaces.append(path_dn)
                    
                    # Parse other path-related children
                    elif 'fvRsCifCont' in child:
                        cif_attrs = child['fvRsCifCont'].get('attributes', {})
                        cif_dn = cif_attrs.get('tDn', '')
                        if cif_dn:
                            interfaces.append(cif_dn)
                
                # Consolidate interfaces
                if interfaces:
                    endpoint['Interface'] = '; '.join(interfaces)
                
                endpoints.append(endpoint)
        
        return endpoints
    
    def export_to_csv(self, data, filename=None):
        """
        Export fvCEp endpoint data to CSV file
        
        Args:
            data: List of fvCEp records
            filename: Output filename (auto-generated if not provided)
            
        Returns:
            str: Path to created CSV file or None if failed
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"fvCEp_endpoints_{timestamp}.csv"
        
        # Ensure it's a Path object
        filepath = Path(filename)
        
        try:
            print(f"\n[*] Processing {len(data)} endpoint records for export...")
            
            # Parse endpoint data
            endpoints = self.parse_endpoint_data(data)
            
            # Write to CSV
            if endpoints:
                print(f"\n[*] Writing {len(endpoints)} endpoints to CSV...")
                
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = [
                        'EPG',
                        'MAC Address',
                        'IP Address',
                        'Interface',
                        'Encapsulation',
                        'Tenant',
                        'Status',
                        'Last Modified',
                        'DN (Distinguished Name)',
                        'Name'
                    ]
                    
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
                    writer.writeheader()
                    
                    # Write rows and fill in missing Tenant field if not extracted
                    for endpoint in endpoints:
                        if 'Tenant' not in endpoint:
                            endpoint['Tenant'] = ''
                        writer.writerow(endpoint)
                
                print(f"[✓] CSV export successful!")
                print(f"[✓] File: {filepath.absolute()}")
                print(f"[✓] Records: {len(endpoints)}")
                
                # Display sample records
                if endpoints:
                    print(f"\n[*] Sample endpoints (first 5):")
                    for i, ep in enumerate(endpoints[:5], 1):
                        print(f"    {i}. MAC: {ep['MAC Address']:20} | EPG: {ep['EPG']:30} | IP: {ep['IP Address']:15}")
                
                return str(filepath.absolute())
            else:
                print("[✗] No endpoint data to export")
                return None
                
        except PermissionError:
            print(f"[✗] Permission denied: Cannot write to {filepath}")
            return None
        except Exception as e:
            print(f"[✗] Export failed: {str(e)}")
            return None
    
    def logout(self):
        """Logout from APIC session"""
        try:
            if self.token:
                url = urljoin(self.apic_url, '/api/aaaLogout.json')
                cookies = {"APIC-cookie": self.token}
                self.session.post(url, cookies=cookies, timeout=self.timeout)
                print("[✓] Logged out from APIC")
        except Exception as e:
            print(f"[!] Logout warning: {str(e)}")


def load_env_file(env_path='.env'):
    """
    Load environment variables from .env file
    
    Args:
        env_path: Path to .env file
        
    Returns:
        dict: Environment variables
    """
    env_vars = {}
    env_file = Path(env_path)
    
    if env_file.exists():
        print(f"[*] Loading credentials from: {env_file.absolute()}")
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
            print(f"[✓] Loaded {len(env_vars)} variables from .env")
        except Exception as e:
            print(f"[!] Error reading .env file: {str(e)}")
    else:
        print(f"[!] No .env file found at {env_file.absolute()}")
    
    return env_vars


def prompt_for_credentials():
    """
    Prompt user for APIC credentials
    
    Returns:
        tuple: (apic_url, username, password, verify_ssl)
    """
    print("\n" + "=" * 70)
    print("APIC Credentials Required")
    print("=" * 70)
    
    apic_url = input("APIC URL [https://APIC.url.com]: ").strip() or "https://APIC.url.com"
    username = input("APIC Username: ").strip()
    password = input("APIC Password: ").strip()
    
    verify_ssl_input = input("Verify SSL certificates? (y/n) [n]: ").strip().lower()
    verify_ssl = verify_ssl_input == 'y'
    
    return apic_url, username, password, verify_ssl


def main():
    """Main execution function"""
    print("\n" + "=" * 70)
    print("APIC fvCEp (Client Endpoint) Data Extraction Tool")
    print("=" * 70)
    print("Purpose: Query APIC REST API and export endpoint data to CSV")
    print("Extracts: EPG, MAC Address, IP, Interface, Encapsulation")
    print("=" * 70)
    
    # Try to load from .env file first
    env_vars = load_env_file('.env')
    
    # Get credentials
    if 'APIC_URL' in env_vars and 'APIC_USERNAME' in env_vars and 'APIC_PASSWORD' in env_vars:
        print("\n[✓] Using credentials from .env file")
        apic_url = env_vars['APIC_URL']
        username = env_vars['APIC_USERNAME']
        password = env_vars['APIC_PASSWORD']
        verify_ssl = env_vars.get('APIC_VERIFY_SSL', 'false').lower() == 'true'
    else:
        print("\n[!] Credentials not found in .env file")
        apic_url, username, password, verify_ssl = prompt_for_credentials()
    
    print(f"\n[*] Configuration:")
    print(f"    APIC URL: {apic_url}")
    print(f"    Username: {username}")
    print(f"    Verify SSL: {verify_ssl}")
    
    # Create client
    client = APICClient(apic_url, username, password, verify_ssl=verify_ssl)
    
    # Authenticate
    print("\n" + "=" * 70)
    print("Authentication")
    print("=" * 70)
    
    if not client.login():
        print("\n[✗] Authentication failed. Exiting.")
        sys.exit(1)
    
    # Fetch data
    print("\n" + "=" * 70)
    print("Data Extraction - Querying fvCEp Endpoints")
    print("=" * 70)
    
    all_data = client.fetch_all_pages(page_size=1000)
    
    if not all_data:
        print("\n[✗] No data retrieved. Exiting.")
        client.logout()
        sys.exit(1)
    
    # Export to CSV
    print("\n" + "=" * 70)
    print("CSV Export")
    print("=" * 70)
    
    csv_file = client.export_to_csv(all_data)
    
    # Cleanup
    client.logout()
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    if csv_file:
        print("[✓] Operation completed successfully!")
        print(f"[✓] Output file: {csv_file}")
        print("\n[*] You can now open this file in Excel, Google Sheets, or any CSV viewer")
        sys.exit(0)
    else:
        print("[✗] Operation failed")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[✗] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
