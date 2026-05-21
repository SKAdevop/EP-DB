# APIC fvCEp (Client Endpoint) Data Extractor

## Overview
This tool queries your Cisco APIC controller to extract all **fvCEp** (Fabric Virtual Client Endpoint) data and exports detailed endpoint information to a CSV file for analysis in Excel or other spreadsheet applications. This is valuable information and is needed when there is a major Fabric Upgrade, APIC Servers, Spines or Leaf replacement operation scheduled or in progress. This information is database of all fabric Endpoints, before a major change.

## What It Does
1. **Authenticates** to your APIC controller using credentials
2. **Queries** the APIC REST API endpoint: `/api/node/class/fvCEp.json`
3. **Paginates** through all results (1000 records per page by default)
4. **Extracts** the following endpoint data:
   - **EPG** - Endpoint Group name (extracted from DN)
   - **MAC Address** - Physical MAC address
   - **IP Address** - Associated IP address (if any)
   - **Interface** - Network interface path/name
   - **Encapsulation** - VLAN/Encapsulation details (VLAN ID or VxLAN)
   - **Tenant** - Tenant name (extracted from DN)
   - **Status** - Current status (created, modified, etc.)
   - **Last Modified** - Timestamp of last modification
   - **Distinguished Name (DN)** - Full DN path in APIC
   - **Name** - Object name

5. **Exports** all data to a CSV file with timestamp

## Prerequisites

### System Requirements
- Windows 7 or later (Windows 10/11 recommended)
- Python 3.7 or higher installed
- Internet connectivity to your APIC controller

### Python Installation
If Python is not installed:
1. Download from: https://www.python.org/downloads/
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH" during installation
4. Click "Install Now"

**Verify Python Installation:**
```
python --version
```

### Required Python Libraries
The script will automatically install the `requests` library if needed.
You can also install manually:
```
pip install requests
```

## Setup Instructions

### Option 1: Using .env File (Recommended)
1. **Create a `.env` file** in the same directory as the script with your APIC credentials:

```
APIC_URL=https://aci.apic.com
APIC_USERNAME=username
APIC_PASSWORD=password
APIC_VERIFY_SSL=false
```

**Note**: In the .env file, use single backslash `\` in the username if using fallback account

2. **Save the file** as `.env` (no prefix, just `.env`)
3. Continue to Usage section below


### Option 2: Manual Execution
1. Open Command Prompt or PowerShell
2. Navigate to the directory containing the script
3. Run:
   ```
   python apic_fvcep_extractor.py
   ```
4. Enter credentials when prompted

## Usage

### With .env File
Simply run:
```bash
python apic_fvcep_extractor.py
```
The script will automatically load credentials from `.env`


### With Manual Prompts
```bash
python apic_fvcep_extractor.py
```
Then enter:
- APIC URL: `https://aci.apic.com`
- Username: `username`
- Password: `password`
- Verify SSL: `n` (unless using valid certificates)

## Output

The script creates a CSV file with the following naming convention:
```
fvCEp_endpoints_YYYYMMDD_HHMMSS.csv
```

**Example**: `fvCEp_endpoints_20260521_142530.csv`

### CSV Columns
| Column | Description |
|--------|-------------|
| EPG | Endpoint Group the endpoint belongs to |
| MAC Address | Physical MAC address of the endpoint |
| IP Address | Associated IP address (if configured) |
| Interface | Network interface/path where endpoint is connected |
| Encapsulation | VLAN ID or VxLAN information |
| Tenant | Tenant that owns the endpoint |
| Status | Current status (created, modified, deleted, etc.) |
| Last Modified | Timestamp of last modification |
| DN (Distinguished Name) | Full APIC Distinguished Name path |
| Name | Name of the endpoint object |

### Example Output
```
EPG,MAC Address,IP Address,Interface,Encapsulation,Tenant,Status,Last Modified,DN,Name
default,00:11:22:33:44:55,10.0.1.100,topology/pod-1/paths-101/pathep-[eth1/1],vlan-100,infra,created,1621545600000,uni/tn-infra/ap-default/epg-default/cep-mac-00:11:22:33:44:55,
prod-epg,aa:bb:cc:dd:ee:ff,10.0.2.50,topology/pod-1/paths-102/pathep-[eth1/2],vlan-200,production,created,1621545601000,uni/tn-production/ap-prod-app/epg-prod-epg/cep-mac-aa:bb:cc:dd:ee:ff,
```

## REST API Details

The script queries this REST API endpoint:
```
GET /api/node/class/fvCEp.json?
    query-target-filter=not(wcard(fvCEp.dn,"__ui_"))&
    rsp-subtree=children&
    order-by=fvCEp.mac|asc&
    page=0&
    page-size=1000
```

**Query Parameters**:
- `query-target-filter`: Excludes UI-generated objects with "__ui_" in DN
- `rsp-subtree`: Includes child objects (IP addresses, interface info)
- `order-by`: Orders results by MAC address in ascending order
- `page-size`: 1000 records per page (optimized for endpoint data)

## Performance Notes

- **Page size**: Default 1000 records per page (optimized for endpoints)
- **Timeout**: 30 seconds per request
- **Speed**: Depends on network and APIC performance
  - 10,000 endpoints: ~10-20 seconds
  - 100,000 endpoints: ~2-5 minutes
  - 1,000,000 endpoints: ~20-40 minutes

## Troubleshooting

### Error: "Python is not installed or not in PATH"
**Solution**: 
1. Install Python from https://www.python.org/downloads/
2. Make sure to check "Add Python to PATH" during installation
3. Restart Command Prompt/PowerShell

### Error: "ModuleNotFoundError: No module named 'requests'"
**Solution**: 
Install the requests library:
```
pip install requests
```

### Error: "Cannot reach aci.apic.com"
**Possible causes**:
- Network connectivity issue
- APIC URL is incorrect
- Firewall blocking the connection
- APIC controller is down

**Solution**:
1. Verify network connectivity: `ping aci.apic.com`
2. Verify APIC is accessible from your browser: https://aci.apic.com
3. Check firewall rules

### Error: "Login failed" or "Authentication error"
**Possible causes**:
- Incorrect username or password
- User account locked
- Session timeout

**Solution**:
1. Verify credentials are correct
2. Test login directly in APIC web UI
3. Check if user account is locked
4. Try disabling SSL verification (`APIC_VERIFY_SSL=false`)

### Error: "SSL: CERTIFICATE_VERIFY_FAILED"
**Solution**: 
Set `APIC_VERIFY_SSL=false` in .env file or answer `n` when prompted

### Script runs but returns no data
**Possible causes**:
- No endpoints in APIC fabric
- Query filter is too restrictive
- User permissions don't allow viewing endpoints

**Solution**:
1. Verify endpoints exist in APIC web UI (Fabric > Inventory > Endpoints)
2. Check user permissions
3. Verify fabric is healthy

## Advanced Options

### Modify Query Parameters
Edit the `query_fvcep()` method in the script:

```python
params = {
    "query-target-filter": 'not(wcard(fvCEp.dn,"__ui_"))',
    "rsp-subtree": "children",
    "order-by": "fvCEp.mac|asc",
    "page": page,
    "page-size": 1000  # Change this value
}
```

### Change Output Columns
Modify the `fieldnames` list in `export_to_csv()` method to add or remove columns.

### Filter by Tenant or EPG
Edit the `parse_endpoint_data()` method to filter endpoints before export.

## Security Notes

⚠️ **Important**: 
- **Never** commit `.env` file to version control
- **Never** share your credentials
- **Never** paste credentials in chat or email
- Use a `.gitignore` file to exclude `.env`:
  ```
  .env
  *.log
  fvCEp_endpoints_*.csv
  ```

## Support & Additional Info

- **APIC Documentation**: https://www.cisco.com/c/en/us/support/cloud-systems-management/application-policy-infrastructure-controller-apic/
- **REST API Reference**: Check your APIC GUI > System > API Inspector
- **Python Requests Library**: https://requests.readthedocs.io/

## License
This script is provided as-is for use with Cisco APIC systems.

## Version History
- **v1.0** (2026-05-11): Initial release
  - fvCEp endpoint data extraction
  - EPG, MAC, IP, Interface, Encap extraction
  - CSV export
  - Pagination support (1000 records/page)
  - .env file support
  - Windows batch launcher

---

**Created**: 2026-05-11 by Shafie A

