from selenium import webdriver
from selenium.webdriver import FirefoxOptions
from selenium.common.exceptions import WebDriverException

from ui.background_tasks import register_task, create_dir_on_hdfs, add_file_to_hdfs, get_file_from_hdfs, remove_file_from_hdfs

class State(object):

    def __init__(self):
        self.web_driver = None
        self.closing_webdriver = False

    def __del__(self):
        if self.web_driver:
            self.web_driver.quit()
            self.web_driver = None
            self.closing_webdriver = True

    def __webdriver_is_closed__(self):
        if not self.web_driver: return True
        try:
            self.web_driver.get('https://example.com/')
        except WebDriverException:
            return True
        return False

    def __start_webdriver__(self):
        if self.__webdriver_is_closed__():
            opts = FirefoxOptions()
            opts.add_argument("--headless")
            self.web_driver = webdriver.Firefox(options=opts)
            self.closing_webdriver = False

    def __stop_webdriver__(self):
        if not self.__webdriver_is_closed__():
            self.web_driver.quit()
            self.web_driver = None
            self.closing_webdriver = True

    def __get_webdriver__(self):
        return self.web_driver

    def __is_webdriver_closing__(self):
        return self.closing_webdriver


def addDirHDFS(request, namenode_host, namenode_container):
    error = ""
    ## Get path from request
    if 'dest_path' in request.POST and request.POST['dest_path'] != "":
        dir_to_create = request.POST['dest_path']
        task = create_dir_on_hdfs.delay(namenode_host, namenode_container, dir_to_create)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"create_dir_on_hdfs")
    else:
        error = "Missing or empty directory path to create"
    return error


def addFileHDFS(request, namenode_host, namenode_container):
    error = ""
    ## Get path from request
    if 'dest_path' in request.POST and request.POST['dest_path'] != "" and 'origin_path' in request.POST and request.POST['origin_path'] != "":
        file_to_add = request.POST['origin_path']
        dest_path = request.POST['dest_path']
        task = add_file_to_hdfs.delay(namenode_host, namenode_container, file_to_add, dest_path)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"add_file_to_hdfs")
    else:
        error = "Missing or empty file path to upload or destination path on HDFS"
    return error


def getFileHDFS(request, namenode_host, namenode_container):
    error = ""
    ## Get path from request
    if 'origin_path' in request.POST and request.POST['origin_path'] != "":
        if 'dest_path' in request.POST: dest_path = request.POST['dest_path']
        else: dest_path = ""
        file_to_download = request.POST['origin_path']
        task = get_file_from_hdfs.delay(namenode_host, namenode_container, file_to_download, dest_path)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"get_file_from_hdfs")
    else:
        error = "Missing or empty file path to download from HDFS or destination path"
    return error


def removeFileHDFS(request, namenode_host, namenode_container):
    error = ""
    ## Get path from request
    if 'dest_path' in request.POST and request.POST['dest_path'] != "":
        path_to_delete = request.POST['dest_path']
        task = remove_file_from_hdfs.delay(namenode_host, namenode_container, path_to_delete)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"remove_file_from_hdfs")
    else:
        error = "Missing or empty path to delete"
    return error