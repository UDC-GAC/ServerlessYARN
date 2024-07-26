import os


class MyUtils:

    @staticmethod
    def create_dir(path):
        if not os.path.exists(path):
            os.makedirs(path)

    @staticmethod
    def clean_log_files(log_dir):
        for filename in os.listdir(log_dir):
            if ".log" in filename:
                log_file = os.path.join(log_dir, filename)
                if os.path.isfile(log_file):
                    os.remove(log_file)
