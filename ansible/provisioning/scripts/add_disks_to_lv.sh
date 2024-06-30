#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

ARGS=($@)
ARGS_NO=$#

if [ $ARGS_NO -lt 4 ]
then
    echo "No disks to add"
    echo "Usage: add_disks_to_lv.sh <vg_name> <lv_name> <disk_1> ... <disk_n> <extra_disk>"
    exit 1
fi

VG=$1
LV=$2
EXTRA_DISK=${ARGS[-1]}

## Remove VG from disk list
DISKS=("${ARGS[@]:1}") 
## Remove LV from disk list
DISKS=("${DISKS[@]:1}")
## Remove extra disk from disk list
DISKS=("${DISKS[@]::${#DISKS[@]}-1}")

## Get current stripes
fields_to_remove=attr,origin,pool_lv,lv_size,data_percent,metadata_percent,move_pv,mirror_log,copy_percent,convert_lv,lv_name,vg_name
current_stripes=$(sudo lvs --noheadings -o+stripes -o-$fields_to_remove $VG/$LV | xargs)
new_stripes=$((current_stripes+${#DISKS[@]}))

check_sync_status(){
    echo "Wait for conversion to finish"
    sleep_seconds=5
    progress="0"
    fields_to_remove=attr,origin,pool_lv,lv_size,data_percent,metadata_percent,move_pv,mirror_log,convert_lv,lv_name,vg_name
    progress=$(sudo lvs --noheadings -o-$fields_to_remove $VG/$LV | xargs)

    echo "Conversion progress: $progress ..."
    while [ -n "$progress" ] && [ "$progress" != "100.00" ] 
    do
        sleep $sleep_seconds
        progress=$(sudo lvs --noheadings -o-$fields_to_remove $VG/$LV | xargs)
        echo "Conversion progress: $progress ..."
    done
}

## Extend VG
echo "sudo pvcreate ${DISKS[*]}"
sudo pvcreate ${DISKS[*]}
echo "sudo vgextend $VG ${DISKS[*]}"
sudo vgextend $VG ${DISKS[*]}

if [ $current_stripes -eq 1 ]
then
    ## Convert linear to R1 first
    echo "sudo lvconvert --type raid1 -y $VG/$LV"
    sudo lvconvert --type raid1 -y $VG/$LV
    ## Wait for conversion to finish
    check_sync_status
fi

## Convert to R5
echo "sudo lvconvert --type raid5_n -y $VG/$LV"
sudo lvconvert --type raid5_n -y $VG/$LV

## Wait for conversion from R0 (or linear) to R5
check_sync_status

## Extend with extra disk and re-convert
echo "sudo pvcreate $EXTRA_DISK"
sudo pvcreate $EXTRA_DISK
echo "sudo vgextend $VG $EXTRA_DISK"
sudo vgextend $VG $EXTRA_DISK
echo "sudo lvconvert --type raid0 --stripes $new_stripes -y $VG/$LV"
sudo lvconvert --type raid0 --stripes $new_stripes -y $VG/$LV

## Wait for conversion from R5 to R0 (actually, to R5 with more stripes)
check_sync_status

## Now actually convert to R0
echo "sudo lvconvert --type raid0 --stripes $new_stripes -y $VG/$LV"
sudo lvconvert --type raid0 --stripes $new_stripes -y $VG/$LV
check_sync_status

## Remove extra disk from VG
echo "sudo vgreduce $VG $EXTRA_DISK"
sudo vgreduce $VG $EXTRA_DISK

## Resize filesystem
echo "sudo resize2fs /dev/$VG/$LV"
sudo resize2fs /dev/$VG/$LV
