# import pickle
# from Config import *

# data_dir = r'D:\vscodefiles\balance\data\tmp_data.pkl'

# tmp_ctx = Ctx()
# tmp_ctx.calibration_name.file_name = '123'

# with open(data_dir, 'wb') as f:
#     pickle.dump(tmp_ctx, f)

# with open(data_dir, 'rb') as f:
#     print(pickle.loads(f.read()))
    

import pickle
import shelve
from Config import *


with open(r'D:\vscode-files\balance\last_ctx.pkl', 'rb') as f:
    print(pickle.loads(f.read()))
    
    