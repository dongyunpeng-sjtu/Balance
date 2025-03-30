call conda activate balance

call pyinstaller main.py ^
-p Main_Window.py ^
-p Ui_main_window_stack.py ^
-p algorithm_vector.py ^
-p algorithm_vector.py ^
-p thread_read.py ^
-p thread_process.py ^
-p utils.py ^
-p Config.py -w ^
--add-data ".\\data\\*;.\\data"