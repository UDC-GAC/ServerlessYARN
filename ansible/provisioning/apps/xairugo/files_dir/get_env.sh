
# NPB run configuration
export NPB_KERNELS_TO_INSTALL=("is" "ft" "mg" "cg" "bt")
export NPB_KERNELS_TO_RUN=("is" "ft" "mg" "cg" "bt")
export NPB_CLASS="A"
export NUM_THREADS_LIST=(1 2 4)



# NPB-C run configuration
export NPB_C_KERNELS_TO_RUN=("cg")
export NPB_C_CLASS="C"
