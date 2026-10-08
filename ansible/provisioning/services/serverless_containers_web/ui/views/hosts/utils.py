import json
import urllib

from ui.forms import AddHostForm, AddDisksToHostsForm


# Keys used by ServerlessContainers in the lent pools of host resources
LENT_FREE_KEY = "free"
LENT_CROSS_KEY_SEPARATOR = "@"
DISK_OPERATIONS = {"disk_read": "read", "disk_write": "write"}

def setAddHostForm(structures, structure_type):
    return {
        'host': AddHostForm(),
        'add_disks_to_hosts': setAddDisksToHostsForm(structures, structure_type)
    }


def setAddDisksToHostsForm(structures, form_action):
    addDisksToHostsForm = AddDisksToHostsForm()

    for host in structures:
        addDisksToHostsForm.fields['host_list'].choices.append((host['name'],host['name']))

    addDisksToHostsForm.helper.form_action = form_action

    return addDisksToHostsForm

def getContainersFromHost(url, host_name):
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
    except urllib.error.HTTPError:
        data = {}

    return [item for item in data if item['subtype'] == 'container' and item['host'] == host_name]

def getLendingRows(resource_label, lent_mapping, container_names, per_core=False):
    """Get one entry per lender with the amount it lends, the amount still available and the amount used by each
    borrower. Lendings already reclaimed (all their values are kept as zero) and removed containers are discarded"""
    rows = []
    for lender in sorted(lent_mapping):
        if lender not in container_names:
            continue

        # CPU shares are lent per core, the rest of resources are lent as a single slot
        lender_entry = lent_mapping[lender]
        slots = lender_entry.items() if per_core else [(None, lender_entry)]
        available, borrowers, cores = 0, {}, {}
        for core, slot in slots:
            for key, value in slot.items():
                if value <= 0:
                    continue
                if key == LENT_FREE_KEY:
                    available += value
                else:
                    borrowers[key] = borrowers.get(key, 0) + value
                if per_core:
                    cores[core] = cores.get(core, 0) + value

        lent = available + sum(borrowers.values())
        if lent <= 0:
            continue

        borrower_rows = []
        for key in sorted(borrowers):
            # Containers using idle disk bandwidth for the opposite operation have keys like 'cont1@disk_write'
            name, _, borrowed_resource = key.partition(LENT_CROSS_KEY_SEPARATOR)
            if name not in container_names:
                continue
            label = "{0} ({1})".format(name, DISK_OPERATIONS.get(borrowed_resource, borrowed_resource)) if borrowed_resource else name
            borrower_rows.append({"name": label, "amount": borrowers[key]})

        rows.append({
            "resource": resource_label,
            "lender": lender,
            "lent": lent,
            "available": available,
            "cores": ", ".join("{0} ({1})".format(core, shares) for core, shares in sorted(cores.items(), key=lambda c: int(c[0]))),
            "borrowers": borrower_rows
        })

    return rows


def getHostLending(host, container_names):
    """Get the resources lent by the containers of a host (cpu, mem and disk bandwidth of each disk)"""
    rows = []
    resources = host.get("resources", {})
    for resource in ["cpu", "mem"]:
        lent_mapping = resources.get(resource, {}).get("lent_mapping", {})
        rows.extend(getLendingRows(resource, lent_mapping, container_names, per_core=(resource == "cpu")))

    for disk_name, disk_info in sorted(resources.get("disks", {}).items()):
        for resource, disk_op in DISK_OPERATIONS.items():
            lent_mapping = disk_info.get("lent_mapping_{0}".format(disk_op), {})
            rows.extend(getLendingRows("{0} ({1})".format(resource, disk_name), lent_mapping, container_names))

    return rows