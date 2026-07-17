# OpenShift Namespace Best-Practices Check

This repo contains a script that audits a single OpenShift namespace for common application architecture issues. It checks for 8 potential problems and prints a detailed report with explanations and recommended next steps for each issue found.

## Checks Performed

1. **Single-Pod Deployments** - flags Deployments, DeploymentConfigs, and StatefulSets running with only one pod
2. **StatefulSets Without a Pod Disruption Budget** - flags multi-replica StatefulSets with no PDB
3. **Backup Volumes** - flags PVCs that appear to be backup volumes but aren't using the correct storage class, and vice versa
4. **StatefulSets With Wrong Storage Class** - flags StatefulSets not using `netapp-block-standard`
5. **Databases Running as Deployments** - flags Deployments whose image name suggests a database workload
6. **Old 'Openshift' Namespace Images** - flags pods using outdated images from the namespace 'openshift'
7. **PDBs With 0 or Fewer Allowed Disruptions** - flags Pod Disruption Budgets that are misconfigured from the number of allowed disruptions
8. **Deprecated DeploymentConfigs** - flags DeploymentConfigs, which are deprecated and should be migrated to Deployments

## Prerequisites

- **Python 3**. Check your version with:
  - Windows (PowerShell/Command Prompt):
  ```
  python --version
  ```
  - Mac/Linux/WSL: 
  ```
  python3 --version
  ```
- **The OpenShift CLI (`oc`)** installed. Confirm it's installed and check your version with:
```
oc version
```
If you do not have `oc` installed, follow these [instructions](https://developer.gov.bc.ca/docs/default/component/platform-developer-docs/docs/openshift-projects-and-access/install-the-oc-command-line-tool/).

## Usage

1. In your terminal, log in to the OpenShift cluster that your [namespace lives on](https://developer.gov.bc.ca/docs/default/component/platform-developer-docs/docs/openshift-projects-and-access/login-to-openshift/). If you are unfamiliar with how to log into OpenShift in terminal, this [video](https://www.youtube.com/watch?v=7tlANUhgGdc) walkthrough demonstrates the `oc login` process.
2. Clone this repository:
```
git clone https://github.com/bcgov/platform-services-namespace-check
```
3. Move into the correct directory:
```
cd platform-services-namespace-check
```
4. Create a virtual environment:
   - Windows (PowerShell/Command Prompt):
   ```
   python -m venv venv
   ```
   - Mac/Linux/WSL:
   ```
   python3 -m venv venv
   ```
5. Activate the virtual environment:
   - Windows (PowerShell):
   ```
   venv\Scripts\Activate.ps1
   ```
   - Windows (Command Prompt):
   ```
   venv\Scripts\activate
   ```
   - Mac/Linux/WSL:
   ```
   source venv/bin/activate
   ```
Your terminal should now show `(venv)` at the start of the line, confirming the virtual environment is active. Make sure you activate it each time you open a new terminal session to run this script.
6. Install the required dependencies:
```
pip install -r requirements.txt
```
7. Run the script:
```
python namespace_best_practices.py
```
8. When prompted, enter the name of the namespace you'd like to check (e.g., d8f105-dev)

## Contact Info

Please contact adin.litman@gov.bc.ca with any questions

