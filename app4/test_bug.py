import sys
import os
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/app4')
from core.config_loader import ConfigLoader
from update.interface_selector import InterfaceSelector

config_loader = ConfigLoader(config_dir='/home/quan/testdata/aspipe_v4/app4/config')
print("All interfaces:", sorted(config_loader.get_available_interfaces()))

