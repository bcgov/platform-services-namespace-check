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

## Usage

1. In your terminal, log in to your OpenShift cluster using `oc login -w`
2. xxxxx

## Contact Info

Please contact adin.litman@gov.bc.ca with any questions

