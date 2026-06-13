import os

DESKTOP_PATH = r"D:\Manga"
MOBILE_PATH = r"/storage/emulated/0/Amain/Manga"
PATH = DESKTOP_PATH if os.name == 'nt' else MOBILE_PATH

JSON_FILE = "manga.json" #in the future i think change to sqllite

TIME_OUT = 5 #wait after problem with a downloading 
WORKER = 8 # multidownloader
ATTEMP = 5 #number of attemp of error