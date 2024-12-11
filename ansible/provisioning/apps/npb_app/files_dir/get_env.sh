# NPB version
export NPB_VERSION="3.4.2"
export NPB_TAR_FILE="NPB${NPB_VERSION}.tar.gz"
export NPB_DOWNLOAD_URL="https://www.nas.nasa.gov/assets/npb/${NPB_TAR_FILE}"

# NPB installation
export NPB_INSTALL_DIR="/opt"
export NPB_HOME="${NPB_INSTALL_DIR}/NPB${NPB_VERSION}"
export NPB_OMP_HOME="${NPB_HOME}/NPB${NPB_VERSION:0:3}-OMP"

# NPB configuration
export NPB_KERNELS_TO_INSTALL=("is" "ft" "mg" "cg" "bt")
export NPB_KERNELS_TO_RUN=("is" "ft" "mg" "cg" "bt")
export NPB_CLASS="D"
export NUM_THREADS=1
export NPB_OUTPUT_DIR={{ bind_dir_on_container }}/npb-output