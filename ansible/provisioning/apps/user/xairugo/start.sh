#!/usr/bin/env bash

function signal_exp {
	python3 /opt/BDWatchdog/TimestampsSnitch/src/timestamping/signal_experiment.py $1 $EXPERIMENT --push
}
function signal_test {
	sleep 6 # This is to allow metrics to be persisted and to avoid 'cutting' the time series early in case of 'end' signal
	# In case os tart it mererly waits 10 seconds before signaling, although an if should be used here
	python3 /opt/BDWatchdog/TimestampsSnitch/src/timestamping/signal_test.py $1 $EXPERIMENT $TEST --push
	sleep 6
}

function run_spark {
	#################
	#### SPARK ######
	#################

	export SPARK_HOME=/opt/spark
	cd /opt/bind/
	
	##############################
	## USING INSTALLED SPARK
	app_log_file="output_spark_standalone"

	TEST="2.SPARK.INSTALLED"
	signal_test "start"
	
	# Run JAR
	$SPARK_HOME/bin/spark-submit \
	  --class org.apache.spark.examples.SparkPi \
	  --master local[*] \
	  --deploy-mode client \
	  $SPARK_HOME/examples/jars/spark-examples_2.12-3.5.5.jar \
	  1000 >> ${app_log_file} 2>&1

	signal_test "end"
	
	
	##############################
	## USING BDEV
	TEST="2.SPARK.BDEV"
	signal_test "start"
		
	wget server:9001/xairugo-bdev.tar.gz
	tar xvf xairugo-bdev.tar.gz
	
	export BDEV_PATH="/opt/bind/bdev"
	export DATA_PATH="/opt/bind/"
	export OUTPUT_PATH="/opt/bind/"
	export JAVA_HOME="/usr/lib/jvm/java-8-openjdk-amd64"
	NUM_WORKERS=4

	
	################
	### KMeans ###
	################
	
	# Generate data
	rm -Rf ${DATA_PATH}/data_kmeans
	TEST="2.SPARK.BDEV.KMEANS.GEN"
	signal_test "start"
	${BDEV_PATH}/solutions/dist/hadoop-3.4.1/bin/hadoop jar ${BDEV_PATH}/solutions/common/bin/rgen.jar \
	-t kmeans -compress false \
	-sampleDir ${DATA_PATH}/data_kmeans/samples -clusterDir ${DATA_PATH}/data_kmeans/cluster \
	-numClusters 10 -numSamples 100000 -samplesPerFile 5000 -sampleDimension 20 >> "${DATA_PATH}/kmeans-gen-output.log" 2>&1
	signal_test "end"
	
	# Execute
	TEST="2.SPARK.BDEV.KMEANS.COMP"
	signal_test "start"
	rm -Rf ${OUTPUT_PATH}/kmeans_out
	${BDEV_PATH}/solutions/dist/spark-3.5.5-bin-hadoop3/bin/spark-submit --class es.udc.gac.sparkbench.ScalaMLlibDenseKMeans \
	--master local[${NUM_WORKERS}] ${BDEV_PATH}/solutions/benchmarks/Spark/src/sparkbench/target/scala-2.12/sparkbench-3.2_2.12.jar \
	--input ${DATA_PATH}/data_kmeans/samples --centers ${DATA_PATH}/data_kmeans/cluster/ \
	--output ${OUTPUT_PATH}/kmeans_out \
	--numIterations 10 --convergenceDelta 0.1 >> "${DATA_PATH}/kmeans-comp-output.log" 2>&1
	signal_test "end"
	
	# Remove results and data
	rm -Rf ${DATA_PATH}/data_kmeans/
	rm -Rf ${OUTPUT_PATH}/kmeans_out 
	
	################
	### Pagerank ###
	################
	
	# Generate data
	rm -Rf /RGen/temp
	rm -Rf ${DATA_PATH}/data_pagerank
	TEST="2.SPARK.BDEV.PAGERANK.GEN"
	signal_test "start"
	${BDEV_PATH}/solutions/dist/hadoop-3.4.1/bin/hadoop jar ${BDEV_PATH}/solutions/common/bin/rgen.jar \
	-t pagerank -b /opt/bind/files_dir/ -n ${DATA_PATH}/data_pagerank \
	-m 2 -r 2 -p 10k  -pbalance -pbalance -o text >> "${DATA_PATH}/pagerank-gen-output.log" 2>&1
	signal_test "end"
	
	# Execute
	TEST="2.SPARK.BDEV.PAGERANK.COMP"
	signal_test "start"
	rm -Rf ${OUTPUT_PATH}/pagerank_out
	${BDEV_PATH}/solutions/dist/spark-3.5.5-bin-hadoop3/bin/spark-submit --class es.udc.gac.sparkbench.ScalaNaivePageRank \
	--master local[${NUM_WORKERS}] ${BDEV_PATH}/solutions/benchmarks/Spark/src/sparkbench/target/scala-2.12/sparkbench-3.2_2.12.jar \
	${DATA_PATH}/data_pagerank/edges ${OUTPUT_PATH}/pagerank_out \
	10000 5 >> "${DATA_PATH}/pagerank-comp-output.log" 2>&1 # Num of pages and num of iterations
	signal_test "end"
	
	# Remove results and data
	rm -Rf ${DATA_PATH}/data_pagerank/
	rm -Rf ${OUTPUT_PATH}/pagerank_out
	
	TEST="2.SPARK.BDEV"
	signal_test "end"
		
	#################
}

function run_stress {
	#################
	#### STRESS #####
	#################
	export STRESS_TIME=20 #120
	new_boundary=20
	curl -X PUT -H "Content-Type: application/json" http://${ORCHESTRATOR_REST_URL}/structure/${CONTAINER_NAME}/limits/cpu/boundary  -d '{"value":"'${new_boundary}'"}'
	

	# Force resources up to the maximum
	curl -X PUT -H "Content-Type: application/json" http://${ORCHESTRATOR_REST_URL}/structure/${CONTAINER_NAME}/guard
	stress -c 4 -t 20 #160
	sleep 10
	
	# Disable serverless for this container
	curl -X PUT -H "Content-Type: application/json" http://${ORCHESTRATOR_REST_URL}/structure/${CONTAINER_NAME}/unguard
	
	TEST="1.STRESS_noserv"
	signal_test "start"
	stress -c 1 -t ${STRESS_TIME}
	stress -c 2 -t ${STRESS_TIME}
	stress -c 3 -t ${STRESS_TIME}
	stress -c 1 -t ${STRESS_TIME}
	signal_test "end"
	touch "/opt/bind/stress-1st-phase-completed.log"
	
	# Enable serverless for this container
	curl -X PUT -H "Content-Type: application/json" http://${ORCHESTRATOR_REST_URL}/structure/${CONTAINER_NAME}/guard

	TEST="1.STRESS_serv"
	signal_test "start"
	stress -c 1 -t ${STRESS_TIME}
	stress -c 2 -t ${STRESS_TIME}
	stress -c 3 -t ${STRESS_TIME}
	stress -c 1 -t ${STRESS_TIME}
	signal_test "end"
	touch "/opt/bind/stress-2nd-phase-completed.log"
	
	
	# Force resources up to the maximum
	stress -c 4 -t 20 #160
	sleep 10
	
	# Change a parameter like the boundary
	new_boundary=5
	curl -X PUT -H "Content-Type: application/json" http://${ORCHESTRATOR_REST_URL}/structure/${CONTAINER_NAME}/limits/cpu/boundary  -d '{"value":"'${new_boundary}'"}'
	
	TEST="1.STRESS_serv_nb"
	signal_test "start"
	stress -c 1 -t ${STRESS_TIME}
	stress -c 2 -t ${STRESS_TIME}
	stress -c 3 -t ${STRESS_TIME}
	stress -c 1 -t ${STRESS_TIME}
	signal_test "end"
	touch "/opt/bind/stress-3rd-phase-completed.log"

	#################
}


function run_npb {
	###############
	#### NPB ######
	###############

	. "${FILES_DIR}/get_env.sh"

	NPB_OUTPUT_DIR="/opt/bind"
	
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
		  /opt/npb/NPB3.4-OMP/bin/${KERNEL}.${NPB_CLASS}.x >> "${NPB_OUTPUT_DIR}/${KERNEL}-output.log" 2>&1
		  END_TEST=$(date +%s%N)
		  EXECUTION_TIME=$(bc <<< "scale=9; $(( END_TEST - START_TEST )) / 1000000000")

		  # Log results
		  echo "[$(date -u "+%Y-%m-%d %H:%M:%S%z")] Execution time for kernel ${KERNEL} (class=${NPB_CLASS}) with ${NUM_THREADS} thread(s): ${EXECUTION_TIME}" | tee -a "${NPB_OUTPUT_DIR}/results.log"
	  done
  
	  signal_test "end"
	done
	
	TEST="3.NPB"
	signal_test "end"
	
	
	TEST="4.NPB-C"
	signal_test "start"
	echo "Starting kernels execution"
	for KERNEL in "${NPB_C_KERNELS_TO_RUN[@]}";do
	  for NUM_THREADS in "${NUM_THREADS_LIST[@]}";do
	  
		  # Set number of threads
		  export OMP_NUM_THREADS="${NUM_THREADS}"

		  echo "[$(date -u "+%Y-%m-%d %H:%M:%S%z")] Running kernel ${KERNEL} (class=${NPB_C_CLASS}) with ${NUM_THREADS} threads" | tee -a "${NPB_OUTPUT_DIR}/results-NPB-C.log"
		  # Run kernel
		  START_TEST=$(date +%s%N)
		  /opt/npb-C/bin/${KERNEL}.${NPB_C_CLASS} >> "${NPB_OUTPUT_DIR}/NPB-C-${KERNEL}-output.log" 2>&1
		  END_TEST=$(date +%s%N)
		  EXECUTION_TIME=$(bc <<< "scale=9; $(( END_TEST - START_TEST )) / 1000000000")

		  # Log results
		  echo "[$(date -u "+%Y-%m-%d %H:%M:%S%z")] Execution time for kernel ${KERNEL} (class=${NPB_CLASS}) with ${NUM_THREADS} thread(s): ${EXECUTION_TIME}" | tee -a "${NPB_OUTPUT_DIR}/results-NPB-C.log"
	  done
	done
	TEST="4.NPB-C"
	signal_test "end"
	
	# Grant permissions to access results outside the container
	chmod -R 777 "${NPB_OUTPUT_DIR}"
	###############
}


function run_transcode {
	TEST="5.TRANSCODE"
	signal_test "start"
	
	OUTPUT_DIR="/opt/bind/transcode"
	mkdir -p ${OUTPUT_DIR}
	cd /opt/bind/transcode
	wget server:9001/froggo.mp4
	FILE_PATH="/opt/bind/froggo.mp4"
	IN_FILE=$(basename ${FILE_PATH})
	OUT_FILE=$(echo ${IN_FILE} | sed 's/mp4/webm/g')
	ffmpeg -i ${IN_FILE} -c:v libvpx-vp9 -crf 30 -b:v 0 -b:a 128k -c:a libopus -threads 16 "${OUTPUT_DIR}/${OUT_FILE}"
	
	signal_test "end"
}

cd /opt/

#exit 1 # uncomment if you want the app to fail to execute it yourself from inside the container

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export FILES_DIR="${SCRIPT_DIR}/files_dir"

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
#run_transcode

signal_exp "end"

# DO NOT REMOVE THIS, ITS IS NECESSARY FOR THE SCRIPT TO SIGNAL A FINISH FOR THE ANSIBLE TASK
exit 0 
