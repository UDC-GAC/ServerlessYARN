import json
import urllib
import atexit

from django.conf import settings
from django.shortcuts import render, redirect
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException


from ui.forms import AddHdfsFileForm, GetHdfsFileForm, AddHdfsDirForm, DeleteHdfsFileForm
from ui.background_tasks import get_pending_tasks_messages

from ui.views.apps.operations import getApps
from ui.views.hdfs.utils import State, addDirHDFS, addFileHDFS, getFileHDFS, removeFileHDFS
from ui.views.hdfs.operations import start_global_hdfs, stop_global_hdfs
from ui.views.core.utils import redirect_with_errors, getHostsNames, getScalerPollFreq, retrieve_global_hdfs_app

webdriver_state = State()

## we force the instance to be the first to cleanup when closing (or reloading) server
# otherwise, webdriver may not quit before closing server and keep browser tabs open
# solution based on: https://stackoverflow.com/questions/14986568/python-how-to-ensure-that-del-method-of-an-object-is-called-before-the-mod
atexit.register(webdriver_state.__stop_webdriver__)

# ------------------------------------ HDFS views ------------------------------------

def hdfs(request):

    def get_entries(url, driver, parent_directory=""):

        hdfs_entries = []

        try:
            driver.get(url)
            driver.refresh() # this refresh is key to avoid getting data from older url and producing an infinite loop
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "table-explorer")))
        except WebDriverException:
            return []
        finally:
            content = driver.page_source.encode('utf-8').strip()
            soup = BeautifulSoup(content,"html.parser")

            found_entries = soup.findAll(class_="explorer-entry")

            for entry in found_entries:
                entry_elements = []

                if parent_directory: entry_elements.append(parent_directory)
                else: entry_elements.append("/")

                entry_path = entry.get('inode-path')
                entry_full_path = "/".join([parent_directory, entry_path])

                ## Skip tmp directory used for YARN jobs
                if entry_full_path == "/tmp": continue

                for element in entry:

                    if element.text.strip():

                        inner_element = element.text.encode('utf-8').decode()
                        inner_entries = []

                        if 'inode-type="DIRECTORY"' in str(element):
                            inner_url = "/".join([url,inner_element])
                            link_tag = '<a inode-type="DIRECTORY" href="{0}">{1}</a>'.format(inner_url, inner_element)
                            entry_elements.append(link_tag)
                            inner_entries = get_entries(inner_url, driver, "/".join([parent_directory, inner_element]))
                        else:
                            entry_elements.append(inner_element)

                ## Add delete form
                entry_elements.append({'get_hdfs_file': GetHdfsFileForm(initial={'origin_path': entry_full_path})})
                entry_elements.append({'del_hdfs_file': DeleteHdfsFileForm(initial={'dest_path': entry_full_path})})

                hdfs_entries.append(entry_elements)
                hdfs_entries.extend(inner_entries)

            return hdfs_entries


    ## Get global hdfs app and its containers
    try:
        response = urllib.request.urlopen(settings.BASE_URL + "/structure/")
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}

    apps, _ = getApps(data_json)
    global_hdfs_app, namenode_container_info = retrieve_global_hdfs_app(apps)

    namenode_container = None
    namenode_host = None
    if namenode_container_info:
        namenode_container = namenode_container_info['name']
        namenode_host = namenode_container_info['host']

    global_hdfs_ready = global_hdfs_app and namenode_host and not webdriver_state.__is_webdriver_closing__()

    context = {
        'global_hdfs_app': global_hdfs_app,
        'global_hdfs_ready': global_hdfs_ready
    }

    if global_hdfs_ready:

        if (len(request.POST) > 0):
            error = None
            errors = []

            if 'operation' in request.POST:
                if request.POST['operation'] == 'add_dir': error = addDirHDFS(request, namenode_host, namenode_container)
                elif request.POST['operation'] == 'add_file': error = addFileHDFS(request, namenode_host, namenode_container)
                elif request.POST['operation'] == 'get_file': error = getFileHDFS(request, namenode_host, namenode_container)
                elif request.POST['operation'] == 'del_file': error = removeFileHDFS(request, namenode_host, namenode_container)

            if error: errors.append(error)

            return redirect_with_errors('hdfs', error)

        namenode_url = 'http://{0}:{1}/explorer.html#'.format("localhost", 55555)

        webdriver_state.__start_webdriver__() ## will only start webdriver if not started yet
        driver = webdriver_state.__get_webdriver__()

        hdfs_entries = get_entries(namenode_url, driver)

        context['data'] = hdfs_entries
        context['namenode_url'] = namenode_url

        context['addDirForm'] = AddHdfsDirForm()
        context['addFileForm'] = AddHdfsFileForm()

    ## Pending tasks
    requests_errors = request.GET.getlist("errors", None)
    requests_successes = request.GET.getlist("success", None)
    requests_info = []
    still_pending_tasks, successful_tasks, failed_tasks = get_pending_tasks_messages()
    requests_errors.extend(failed_tasks)
    requests_successes.extend(successful_tasks)
    requests_info.extend(still_pending_tasks)

    context['requests'] = {}
    context['requests']['errors'] = requests_errors
    context['requests']['successes'] = requests_successes
    context['requests']['info'] = requests_info
    context['config'] = settings.PLATFORM_CONFIG

    return render(request, 'hdfs.html', context)


def manage_global_hdfs(request):
    # Common parameters
    resources = ["cpu", "mem"]
    if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']: resources.extend(["disk_read", "disk_write"])
    url = settings.BASE_URL + "/structure/"
    app_name = "global_hdfs"
    nn_container_prefix = "namenode"
    dn_container_prefix = "datanode"

    state = request.POST['manage_global_hdfs']
    if state == "hdfs_on":
        error = start_global_hdfs(request, app_name, url, resources, nn_container_prefix, dn_container_prefix, webdriver_state)
    else:
        error = stop_global_hdfs(request, app_name, url, resources, nn_container_prefix, webdriver_state)

    return redirect('hdfs')



