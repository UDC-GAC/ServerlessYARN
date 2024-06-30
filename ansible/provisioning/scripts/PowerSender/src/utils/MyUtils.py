import os


class MyUtils:

    @staticmethod
    def create_dir(path):
        if not os.path.exists(path):
            os.makedirs(path)

    @staticmethod
    def clean_log_file(log_file):
        if os.path.isfile(log_file):
            os.remove(log_file)
