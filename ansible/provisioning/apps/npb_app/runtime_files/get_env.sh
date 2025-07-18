# NPB general
export NPB_VERSION="3.4.2"
export NPB_HOME="${NPB_INSTALL_DIR}/NPB${NPB_VERSION}"
export NPB_OMP_HOME="${NPB_HOME}/NPB${NPB_VERSION:0:3}-OMP"

# NPB runtime configuration
export NPB_KERNELS=("is" "ft" "mg" "cg" "bt")
export NPB_CLASSES=("C")
export NUM_THREADS=1
export NPB_OUTPUT_DIR={{ bind_dir_on_container }}/output_dir