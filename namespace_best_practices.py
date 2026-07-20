import requests
import subprocess
import textwrap


def make_api_call(url):
    try: 
        api_call = requests.get(url, headers=openshiftheader).json()
        return api_call
    except Exception as e:
        print("Error:", e)
        return {'items': []}
        
while True:
    # Ask the user for their namespace
    namespace_name = input("Enter your namespace: ").strip()

    if not namespace_name:
        print("Please enter a namespace.")
        continue

    print(f"You entered: {namespace_name}")

    # Check if they're logged in via oc whoami
    # If not logged in, print a message and continue the loop (skip to next iteration)
    whoami_result = subprocess.run(['oc', 'whoami'], capture_output=True, text=True)
    if whoami_result.returncode:
        print("You're not logged in to the cluster, please run oc login -w")
        continue

    # Fetch the token and server URL
    token_result = subprocess.run(['oc', 'whoami', '--show-token'], capture_output=True, text=True)
    token = token_result.stdout.strip()
    server_result = subprocess.run(['oc', 'whoami', '--show-server'], capture_output=True, text=True)
    openshifturl = server_result.stdout.strip()
    openshiftheader = {'Authorization': 'Bearer ' + token}
    
    # Validate the namespace (make the API call, check for 401/404)
    namespace_url = openshifturl + '/api/v1/namespaces/' + namespace_name
    namespace_response = make_api_call(namespace_url)
    
    # If 401 -> print a message telling them to log in, then continue the loop
    if namespace_response.get('code', None) == 401:
        print("Token is incorrect or for the wrong cluster")
        continue

    # If 404 -> print a message telling them the namespace is invalid, then continue the loop
    if namespace_response.get('code', None) == 404:
        print("Namespace doesn't exist or is not accessible with this token")  
        continue

    # If neither -> break out of the loop, since everything is valid
    break

deployment_url = openshifturl + '/apis/apps/v1/namespaces/' + namespace_name + '/deployments'
deployment_response = make_api_call(deployment_url)

dconfig_url = openshifturl + '/apis/apps.openshift.io/v1/namespaces/' + namespace_name + '/deploymentconfigs'
dconfig_response = make_api_call(dconfig_url)

sset_url = openshifturl + '/apis/apps/v1/namespaces/' + namespace_name + '/statefulsets'
sset_response = make_api_call(sset_url)

pdb_url = openshifturl + '/apis/policy/v1/namespaces/' + namespace_name + '/poddisruptionbudgets'
pdb_response = make_api_call(pdb_url)

pvc_url = openshifturl + '/api/v1/namespaces/' + namespace_name + '/persistentvolumeclaims'
pvc_response = make_api_call(pvc_url)

podlist_url = openshifturl + '/api' + '/v1' + '/namespaces/' + namespace_name + '/pods'
podlist_response = make_api_call(podlist_url)

# Functions:

# Check 1:

def single_pod_deployments(deployment_response, dconfig_response, sset_response):
    results_problem = {'deployments': [], 'configs': [], 'statefulsets': []}
    results_potential = {'deployments': [], 'configs': [], 'statefulsets': []}
    skip_words = ['worker', 'backup', 'schedule', 'cron']
    
    # Loop through deployments:
    for deployment in deployment_response['items']:
        deployment_replicas = deployment['spec'].get('replicas')
        deployment_status = deployment['status'].get('readyReplicas')
        deployment_name = deployment['metadata']['name']


        # Get all 1 pod deployments:
        if deployment_replicas and deployment_replicas == 1 and deployment_status and deployment_status > 0:
            skip = False
            for word in skip_words:
                if word in deployment_name: 
                    skip = True

            if not skip: 
                results_problem['deployments'].append(deployment_name)

            else: 
                results_potential['deployments'].append(deployment_name)

    # Loop through deployment configs:
    for dconfig in dconfig_response['items']:
        dconfig_replicas = dconfig['spec'].get('replicas')
        dconfig_status = dconfig['status'].get('readyReplicas')
        dconfig_name = dconfig['metadata']['name']
        
        # Get all 1 pod deployment configs:
        if dconfig_replicas and dconfig_replicas == 1 and dconfig_status and dconfig_status > 0:
            skip = False
            for word in skip_words:
                if word in dconfig_name: 
                    skip = True

            if not skip: 
                results_problem['configs'].append(dconfig_name)

            else: 
                results_potential['configs'].append(dconfig_name)


    # Loop through statefulsets: 
    for sset in sset_response['items']:
        sset_replicas = sset['spec'].get('replicas')
        sset_status = sset['status'].get('readyReplicas')
        sset_labels = sset['metadata'].get('labels', {})
        sset_name = sset['metadata']['name']

        # Get all 1 pod statefulsets:
        if sset_replicas and sset_replicas == 1 and sset_status and sset_status > 0 and 'postgres-operator.crunchydata.com/cluster' not in sset_labels:
            skip = False
            for word in skip_words:
                if word in sset_name: 
                    skip = True

            if not skip: 
                results_problem['statefulsets'].append(sset_name) 

            else: 
                results_potential['statefulsets'].append(sset_name)

    return results_problem, results_potential


# Check 2:

def find_sset_without_pdb(sset_response, pdb_response):
    no_ssetpdb_namespace = []
    # Loop through statefulsets: 
    for sset in sset_response['items']:
        sset_status = sset['status'].get('readyReplicas')
        sset_labels = sset['metadata'].get('labels', {})
        sset_name = sset['metadata']['name']

        if sset_status and sset_status > 1:
            has_pdb = False
            sset_selector = sset['spec']['selector'].get('matchLabels', {})
            for pdb in pdb_response['items']:
                pdb_selector = pdb['spec']['selector'].get('matchLabels', {})
                all_match = True
                for key in sset_selector.keys():
                    if sset_selector[key] != pdb_selector.get(key):
                        all_match = False
                if all_match:
                    has_pdb = True
            if not has_pdb:
                no_ssetpdb_namespace.append(sset_name)
    return no_ssetpdb_namespace


# Check 3: 

def find_backup_volumes(pvc_response):
    backup_words = ['backup', 'back_up', 'bkup', 'repo', 'dump']
    flagged_backupvolumes1 = []
    flagged_backupvolumes2 = []

    # Flagging flag backup volumes that do not use the netapp-file-backup storageclassname
    for pvc in pvc_response['items']:
        pvc_name = pvc['metadata']['name']
        storageclassname = pvc['spec'].get('storageClassName', None)

        has_backup_word = False
        for word in backup_words:
            if word in pvc_name:
                has_backup_word = True

        if has_backup_word and 'verification' not in pvc_name:
            if storageclassname != 'netapp-file-backup':
                flagged_backupvolumes1.append(pvc_name)

        # Flagging volumes that have a netapp-file-backup PVC but whose name does NOT contain a           backup word:
        if storageclassname == 'netapp-file-backup' and not has_backup_word:
            flagged_backupvolumes2.append(pvc_name)

    return flagged_backupvolumes1, flagged_backupvolumes2


# Check 4:

def find_sset_wrong_storage(sset_response):
    wrong_storageclass = []
    for sset in sset_response['items']:
        if len(sset['spec'].get('volumeClaimTemplates', [])) > 0:
            statefulset_name = sset['metadata']['name']
            volumeclaimtemplates = sset['spec']['volumeClaimTemplates']
                
            for template in volumeclaimtemplates:
                storageclassname = template['spec'].get('storageClassName', None)
    
                if storageclassname and storageclassname != 'netapp-block-standard':
                    display_class = storageclassname if storageclassname else 'default (netapp-file-standard)'
                    wrong_storageclass.append({'statefulset': statefulset_name, 'storageclass': display_class})

    return wrong_storageclass


# Check 5: 

def check_databases_sset(deployment_response):
    db_words = ['postgres', 'patroni', 'mongo', 'redis', 'sql', 'maria', 'memcached', 'database', 'db']
    flagged_deployments = []

    for deployment in deployment_response['items']:
        deployment_name = deployment['metadata']['name']
        for container in deployment['spec']['template']['spec']['containers']:
            image_name = container['image'].split('/')[-1].split('@')[0].split(':')[0]
            check_name = image_name.replace('sandbox', '').replace('feedback', '')

            matching_word = False
            for word in db_words:
                if word in check_name:
                    matching_word = True

            if matching_word or image_name == 'db':
                flagged_deployments.append({'deployment': deployment_name, 'image': image_name})

    return flagged_deployments


# Check 6: 

def find_old_openshift_images(podlist_response):
    flagged_pods = []
    for pod in podlist_response['items']:
        pod_name = pod['metadata']['name']
        found_openshift_image = False
        matching_images = []
        for container in pod['spec']['containers']:
            image_name = container['image']
            if '/openshift/' in image_name:
                found_openshift_image = True
                matching_images.append(image_name)

        if found_openshift_image:
            flagged_pods.append({'pod name': pod_name, 'image': matching_images})
    return flagged_pods

    
# Check 7:

def check_pdb_disruptions(pdb_response, podlist_response):
    bad_pdbs = []
    for pdb in pdb_response['items']:
        pdb_name = pdb['metadata']['name']
        pdb_status = pdb['status'].get('disruptionsAllowed', 1)
        pdb_selector = pdb['spec']['selector'].get('matchLabels', {})

        if pdb_status <= 0:
            has_running_pods = False
            for pod in podlist_response['items']:
                pod_labels = pod['metadata'].get('labels', {})
                all_match = True
                for key in pdb_selector.keys():
                    if pdb_selector[key] != pod_labels.get(key):
                        all_match = False
                if all_match:
                    has_running_pods = True

            bad_pdbs.append({'pdb': pdb_name, 'has_running_pods': has_running_pods})
    return bad_pdbs
                    

# Check 8:

def find_dconfigs(dconfig_response):
    all_dconfigs = []
    for dconfig in dconfig_response['items']:
        dconfig_name = dconfig['metadata']['name']
        all_dconfigs.append(dconfig_name)
    return all_dconfigs


# Run all checks:

results_problem, results_potential = single_pod_deployments(deployment_response, dconfig_response, sset_response)
no_pdb_ssets = find_sset_without_pdb(sset_response, pdb_response)
flagged_backupvolumes1, flagged_backupvolumes2 = find_backup_volumes(pvc_response)
wrong_storageclass = find_sset_wrong_storage(sset_response)
flagged_db_deployments = check_databases_sset(deployment_response)
flagged_openshift_images = find_old_openshift_images(podlist_response)
bad_pdbs = check_pdb_disruptions(pdb_response, podlist_response)
all_dconfigs = find_dconfigs(dconfig_response)

# --- Print helpers ---

def print_header(title):
    print(f'\n\033[1m{"=" * 60}\033[0m')
    print(f'\033[1m  {title}\033[0m')
    print(f'\033[1m{"=" * 60}\033[0m')

def print_subheader(title):
    print(f'\n\033[1m  {title}\033[0m')
    print(f'  {"-" * 40}')

def print_none():
    print('    ✓ None')

def print_item(text):
    print(f'    • {text}')

def print_explanation(text, width=100):
    print()
    for paragraph in text.split('\n\n'):
        if paragraph.startswith('  •'):
            print(textwrap.fill(paragraph, width=width, subsequent_indent='    ', 
                              break_long_words=False, break_on_hyphens=False))
        else:
            print(textwrap.fill(paragraph, width=width, break_long_words=False, 
                              break_on_hyphens=False))
        print()

# --- Namespace banner + intro ---
print(f'\033[1mNAMESPACE: {namespace_name}\033[0m')
print_explanation(
    "This script checks your namespace for 8 common application architecture issues. "
    "Each issue identified includes an explanation and recommended next steps.")

# --- Check 1: Single Pod ---
print_header('CHECK 1: SINGLE-POD DEPLOYMENTS')

check1_explanation = (
    "Running a single pod Deployment, DeploymentConfig, or StatefulSet means your application has "
    "no redundancy and if your pod goes down, your application goes down with it. We recommend a "
    "minimum of 3 pods for production deployments. It's also worth noting that due to regular "
    "OpenShift cluster maintenance, pods can be evicted or shut down at any time, so a single-pod "
    "deployment that has been stable so far may still experience an outage in the future. Single-pod "
    "deployments may be down for as much as 10% of the time, whereas multi-node deployments benefit "
    "from 99.5% target uptime on Silver.\n\n"
    "In many cases, scaling up is straightforward: you can increase your pod count directly in "
    "OpenShift and things will work as expected. That said, there are some important exceptions to "
    "keep in mind:\n\n"
    "  • Databases and certain stateful applications require special handling.\n\n"
    "  • If your application is managed by an operator, please consult the operator's documentation "
    "and allow the operator to manage the scaling process rather than doing it manually.\n\n"
    "If you're unsure how your application will behave, we strongly encourage testing in a lower "
    "environment (e.g., dev) first. Scale up there and observe how your application responds — this "
    "often makes it clear why high availability matters.\n\n"
    "The results below are split into \"high priority to check\" and \"medium priority to check\" "
    "based on the name of the deployment. Medium priority deployments "
    "contain a keyword in their name that suggests a single-pod setup may be intentional (such as "
    "\"backup\", \"cron\", or \"worker\"), whereas high priority deployments do not contain these "
    "job-like keywords.\n\n"
    "Since the results are split solely based on the name of the deployment, it can't determine your actual use case with "
    "certainty, and thus it is possible that a deployment labeled as high priority is appropriately "
    "set up with a single pod. So please treat the categorization as a guide rather than a final "
    "answer.")
print_explanation(check1_explanation)

print_subheader('HIGH PRIORITY TO CHECK')
if any(results_problem[k] for k in results_problem):
    first = True
    for resource_type, names in results_problem.items():
        if names:
            if not first:
                print()
            print(f'    \033[1m{resource_type.capitalize()}:\033[0m')
            for name in names:
                print_item(name)
            first = False
else:
    print_none()

print_subheader('MEDIUM PRIORITY TO CHECK')
if any(results_potential[k] for k in results_potential):
    first = True
    for resource_type, names in results_potential.items():
        if names:
            if not first:
                print()
            print(f'    \033[1m{resource_type.capitalize()}:\033[0m')
            for name in names:
                print_item(name)
            first = False
else:
    print_none()

# --- Check 2: StatefulSets without PDB ---
print_header('CHECK 2: STATEFULSETS WITHOUT PDB')

check2_explanation = (
    "Cluster maintenance happens during regular business hours, and applications should be able to "
    "handle worker nodes being taken offline for updates. If your application takes time to pass its "
    "readiness and liveness probes, a relocated pod may still be starting up when another pod in the "
    "same StatefulSet is terminated — causing an outage even though you're running multiple replicas. "
    "A Pod Disruption Budget (PDB) prevents this by defining the maximum number of pods that are "
    "allowed to be offline simultaneously. We recommend adding a properly configured PDB to any "
    "StatefulSet running more than one replica.\n\n"
    "Below are the StatefulSets in your namespace running more than one replica without a PDB:")
print_explanation(check2_explanation)

if no_pdb_ssets:
    for sset in no_pdb_ssets:
        print_item(sset)
else:
    print_none()

check2_followup = (
    "For more information on setting up a properly configured PDB, see: "
    "https://developer.gov.bc.ca/docs/default/component/platform-developer-docs/docs/build-deploy-and-maintain-apps/maintain-an-application/#pdbs-pod-disruption-budgets")

print_explanation(check2_followup)

# --- Check 3: Backup Volumes ---
print_header('CHECK 3: BACKUP VOLUMES')
check3_explanation = (
    "This check looks at PersistentVolumeClaims (PVCs) used for backups. PVCs intended for backup "
    "storage should use the netapp-file-backup storage class, whereas PVCs not used for backup storage "
    "should not use the netapp-file-backup storage class.\n\n"
    "Two situations are flagged below:\n\n"
    "  • PVCs whose name suggests they're used for backups (e.g. containing \"backup\", \"repo\", "
    " or \"dump\") but are not using the netapp-file-backup storage class.\n\n"
    "  • PVCs that are using the netapp-file-backup storage class but whose name doesn't suggest "
    "they're a backup volume.\n\n"
    "Either case may indicate a misconfigured or mislabeled volume worth double-checking.")
print_explanation(check3_explanation)

print_subheader('Backup volumes without netapp-file-backup storageclass')
if flagged_backupvolumes1:
    for pvc in flagged_backupvolumes1:
        print_item(pvc)
else:
    print_none()

print_subheader('Volumes with netapp-file-backup storageclass but not a backup volume')
if flagged_backupvolumes2:
    for pvc in flagged_backupvolumes2:
        print_item(pvc)
else:
    print_none()

# --- Check 4: Database Storage Class ---
print_header('CHECK 4: STATEFULSETS WITH WRONG STORAGE CLASS')
check4_explanation = (
    "StatefulSets are typically used for databases and other stateful applications that require "
    "persistent storage.\n\n"
    "Database workloads should use the netapp-block-standard storage class, which is provisioned "
    "specifically for database use cases and provides the consistent I/O performance that a database "
    "requires. Note that there may be legitimate reasons for a StatefulSet to use a different "
    "storage class - this check is intended to flag items for review rather than indicate a "
    "definitive problem. Below are the StatefulSets in your namespace whose PersistentVolumeClaims "
    "are using a storage class other than netapp-block-standard:")
print_explanation(check4_explanation)

if wrong_storageclass:
    grouped = {}
    for item in wrong_storageclass:
        sc = item['storageclass']
        if sc not in grouped:
            grouped[sc] = []
        grouped[sc].append(item['statefulset'])
    for sc, ssets in grouped.items():
        print(f'\n    \033[1mStorage Class: {sc}\033[0m')
        for sset in ssets:
            print_item(sset)
else:
    print_none()

# --- Check 5: Databases as Deployments ---
print_header('CHECK 5: DATABASES RUNNING AS DEPLOYMENTS')
check5_explanation = (
    "Databases and other stateful applications should run as StatefulSets rather than Deployments.\n\n"
    "This check scans the container image names of your Deployments for keywords commonly associated "
    "with database workloads (such as \"postgres\", \"mongo\", \"redis\", and \"mysql\"). "
    "Below are the Deployments in your namespace whose container image names suggest they may be "
    "running a database workload:")
print_explanation(check5_explanation)

if flagged_db_deployments:
    for item in flagged_db_deployments:
        print_item(f'Deployment: {item["deployment"]} | Image: {item["image"]}')
else:
    print_none()

# --- Check 6: Old OpenShift Images ---
print_header("CHECK 6: OLD 'OPENSHIFT' NAMESPACE IMAGES")
check6_explanation = (
    "The namespace 'openshift' contains a set of commonly used base images (such as Node.js) that "
    "have not been updated in some time. Using these images is not recommended as they contain "
    "outdated dependencies and security vulnerabilities.\n\n"
    "We recommend migrating to actively maintained images from a trusted source such as the "
    "Red Hat container catalog or your own maintained images. Below are the pods in your "
    "namespace that are currently using images from the 'openshift' namespace:")
print_explanation(check6_explanation)

if flagged_openshift_images:
    for item in flagged_openshift_images:
        clean_images = [image.split('/openshift/')[-1].split('@')[0].split(':')[0] for image in item['image']]
        print_item(f'Pod: {item["pod name"]} | Image: {", ".join(clean_images)}')
else:
    print_none()

# --- Check 7: PDB Disruptions ---
print_header('CHECK 7: PDBS WITH 0 OR FEWER ALLOWED DISRUPTIONS')
check7_explanation = (
    "A Pod Disruption Budget (PDB) with zero or fewer allowed disruptions means that no pods can "
    "be automatically taken down at any time — including during cluster maintenance. This can block "
    "platform maintenance operations, preventing worker nodes from being taken offline for updates "
    "and potentially disrupting the entire cluster.\n\n"
    "Below are the PDBs in your namespace with zero or fewer allowed disruptions, along with "
    "whether they have any running pods. PDBs with running pods are the most pressing concern "
    "as they are actively blocking potential maintenance operations. PDBs without running pods do "
    "not pose an immediate risk to maintenance, but it is generally good practice to remove unused "
    "objects from your namespace.")
print_explanation(check7_explanation)

with_pods = [p for p in bad_pdbs if p['has_running_pods']]
without_pods = [p for p in bad_pdbs if not p['has_running_pods']]
print_subheader('With running pods')
if with_pods:
    for p in with_pods:
        print_item(p["pdb"])
else:
    print_none()
print_subheader('Without running pods')
if without_pods:
    for p in without_pods:
        print_item(p["pdb"])
else:
    print_none()

# --- Check 8: Deprecated DeploymentConfigs ---
print_header('CHECK 8: DEPRECATED DEPLOYMENT CONFIGS')
check8_explanation = (
    "DeploymentConfigs have been deprecated and will be removed in a future version of OpenShift. "
    "While no specific removal date has been announced, migrating to Deployments sooner rather than "
    "later is strongly recommended to ensure the continuity of your application.\n\n"
    "We recommend migrating your DeploymentConfigs to Deployments at your earliest convenience. "
    "Below are the DeploymentConfigs found in your namespace:")
print_explanation(check8_explanation)

if all_dconfigs:
    for name in all_dconfigs:
        print_item(name)
else:
    print_none()