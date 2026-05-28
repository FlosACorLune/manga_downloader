import os

DESKTOP_PATH = r"D:\TESTMANGA"
#DESKTOP_PATH = r"E:\manga"
MOBILE_PATH = r"/storage/emulated/0/Amain/Manga"
PATH = DESKTOP_PATH if os.name == 'nt' else MOBILE_PATH

TIME_OUT = 5 #wait after problem with a downloading 
WORKER = 8 # multidownloader
ATTEMP = 5 #number of attemp of error
DELAY = 0.2 #5 queries per second  1/0.2
USE_JXL = True