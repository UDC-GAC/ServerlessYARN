IFS='-' read -ra ALLOWED_CORES <<< $(cat /proc/self/status | grep Cpus_allowed_list | awk '{print $2}')
if [[ -z ${ALLOWED_CORES[1]} ]]; then
  AUX=1
else
  AUX=$(( ALLOWED_CORES[1] - ALLOWED_CORES[0] ))
fi
export FIRST_THREAD=${ALLOWED_CORES[0]}
export MAX_THREADS=${AUX}