from genericpath import isdir
import time
import zipfile
import os


ignores = [
    '.git',
    '__pycache__',
    'build',
    'dist',
    'history',
    'logs',
    'test',
    'pkl'
]
os.chdir(os.path.dirname(__file__))
# print(os.getcwd())
time_str = time.strftime('%m%d', time.localtime())
zip = zipfile.ZipFile(f'./history/Balance-{time_str}.zip', 'w', zipfile.ZIP_DEFLATED)
dir_name = './'

def check_ignore(name):
    for ignore in ignores:
        if name.find(ignore) != -1: # ignore
            return True
    return False

def zip_files(name):
    for item in os.listdir(name):
        file_path = os.path.join(name, item)
        if check_ignore(file_path):
            continue
        zip.write(file_path)
        print(file_path)
        if os.path.isdir(item):
            zip_files(file_path)

zip_files(dir_name)




    

    
            
            
    
