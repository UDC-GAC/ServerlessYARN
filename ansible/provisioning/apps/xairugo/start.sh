#!/usr/bin/env bash

function signal_exp {
	python3 /opt/BDWatchdog/TimestampsSnitch/src/timestamping/signal_experiment.py $1 $EXPERIMENT --push
}
function signal_test {
	sleep 10 # This is to allow metrics to be persisted and to avoid 'cutting' the time series early in case of 'end' signal
	# In case os tart it mererly waits 10 seconds before signaling, although an if should be used here
	python3 /opt/BDWatchdog/TimestampsSnitch/src/timestamping/signal_test.py $1 $EXPERIMENT $TEST --push
}

function run_spark {
	#################
	#### SPARK ######
	#################

	export SPARK_HOME=/opt/spark
	TEST="2.SPARK"

	output_file="output_spark_standalone_`date +%d-%m-%y--%H-%M-%S`"
	app_log_file="app_log_spark_standalone_`date +%d-%m-%y--%H-%M-%S`"

	signal_test "start"

	# Run JAR
	$SPARK_HOME/bin/spark-submit \
	  --class org.apache.spark.examples.SparkPi \
	  --master local[*] \
	  --deploy-mode client \
	  $SPARK_HOME/examples/jars/spark-examples_2.12-{{ spark_version }}.jar \
	  10000 2> $app_log_file 1>$output_file

	signal_test "end"

	#################
}

function run_stress {
	#################
	#### STRESS #####
	#################
	export STRESS_TIME=60
	
	TEST="1.STRESS_1c_serv"
	signal_test "start"
	stress -c 1 -t ${STRESS_TIME}
	signal_test "end"

	TEST="1.STRESS_2c_serv"
	signal_test "start"
	stress -c 2 -t ${STRESS_TIME}
	signal_test "end"
	
	# Disable serverless for this container
	curl -X PUT -H "Content-Type: application/json" http://${ORCHESTRATOR_REST_URL}/structure/${CONTAINER_NAME}/unguard
	
	TEST="1.STRESS_1c_noserv"
	signal_test "start"
	stress -c 1 -t ${STRESS_TIME}
	signal_test "end"

	TEST="1.STRESS_2c_noserv"
	signal_test "start"
	stress -c 2 -t ${STRESS_TIME}
	signal_test "end"
	#################
}


function run_npb {
	###############
	#### NPB ######
	###############

	. "${FILES_DIR}/npb_env.sh"

	# If some kernels are specified, overwrite default kernels
	if [ -n "${1}" ];then
	  IFS=',' read -ra NPB_KERNELS_TO_RUN <<< "${1}"
	fi

	# If a number of threads is specified, overwrite NUM_THREADS
	if [ -n "${2}" ];then
	  NUM_THREADS="${2}"
	fi

	# Clean/Create output directory
	rm -rf "${NPB_OUTPUT_DIR}/*"
	mkdir -p "${NPB_OUTPUT_DIR}"
	
	TEST="3.NPB"
	signal_test "start"
	
	echo "Starting kernels execution"
	for KERNEL in "${NPB_KERNELS_TO_RUN[@]}";do
	  TEST="3.NPB_${KERNEL}"
	  
	  signal_test "start"
	  
	  for NUM_THREADS in "${NUM_THREADS_LIST[@]}";do
	  
		  # Set number of threads
		  export OMP_NUM_THREADS="${NUM_THREADS}"

		  echo "[$(date -u "+%Y-%m-%d %H:%M:%S%z")] Running kernel ${KERNEL} (class=${NPB_CLASS}) with ${NUM_THREADS} threads" | tee -a "${NPB_OUTPUT_DIR}/results.log"
		  # Run kernel
		  START_TEST=$(date +%s%N)
		  ${NPB_OMP_HOME}/bin/${KERNEL}.${NPB_CLASS}.x >> "${NPB_OUTPUT_DIR}/${KERNEL}-output.log" 2>&1
		  END_TEST=$(date +%s%N)
		  EXECUTION_TIME=$(bc <<< "scale=9; $(( END_TEST - START_TEST )) / 1000000000")

		  # Log results
		  echo "[$(date -u "+%Y-%m-%d %H:%M:%S%z")] Execution time for kernel ${KERNEL} (class=${NPB_CLASS}) with ${NUM_THREADS} thread(s): ${EXECUTION_TIME}" | tee -a "${NPB_OUTPUT_DIR}/results.log"
	  done

	  sleep 10
	  
	  signal_test "end"
	done
	
	TEST="3.NPB"
	signal_test "end"
	
	# Grant permissions to access results outside the container
	chmod -R 777 "${NPB_OUTPUT_DIR}"
	###############
}



cd {{ bind_dir_on_container }}

#exit 1 # uncomment if you want the app to fail to execute it yourself from inside the container

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export FILES_DIR="${SCRIPT_DIR}/myfiles"

########################
#### TIMESTAMPING ######
########################

export MONGODB_IP="server"
source /opt/BDWatchdog/set_pythonpath.sh

EXPERIMENT="EXP_XAIRUGO"
signal_exp "start"

########################
#### ORCHESTRATOR ######
########################

export ORCHESTRATOR_REST_URL="server:5000"
export CONTAINER_NAME=$(hostname)


#######################
#### experiments ######
#######################

run_stress
#run_spark
#run_npb

signal_exp "end"
