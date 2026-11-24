## Big Data (Hadoop / Spark / HDFS) specific code of the web interface
##   - resources.py: resources calculation for Hadoop clusters
##   - playbooks.py: calls to the Big Data Ansible tasks (check ansible/provisioning/tasks/bigdata)
##   - data_locality.py: support for the 'Data-locality' allocation policy (based on global HDFS data)
##   - start.py: Big Data specific steps when adding/starting apps
##   - forms.py: Big Data specific forms and form options (e.g., global HDFS options when starting apps)
## Background tasks are kept in ui/background/bigdata_tasks.py, along with the generic ones

from django.conf import settings

SUPPORTED_FRAMEWORKS = {"hadoop", "spark"}

DEFAULT_HDFS_VALUES = {
    "local_output": "/user/{username}",
    "global_output": "/user/{username}"
}

def is_bigdata_app(app_type):
    """Whether the app is deployed as a Hadoop cluster, i.e., with a master container and worker containers"""
    return app_type in settings.VARS_CONFIG['bigdata_app_types']

def get_framework_app_type(framework):
    """Get the app type of a Big Data app from its framework (e.g., 'spark' --> 'spark_app')"""
    if framework not in SUPPORTED_FRAMEWORKS:
        raise Exception("{0} framework not supported, currently supported frameworks: {1}".format(framework, SUPPORTED_FRAMEWORKS))
    return "{0}_app".format(framework)
