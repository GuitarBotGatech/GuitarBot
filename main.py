from Model import Model
from View import View
from Controller import Controller
import os

def main():
    view = View()
    model = Model()
    controller = Controller(view, model)
    controller.start()

# run this script to start the UI
if __name__ == "__main__":
    # set root directory as 'GuitarBot/UI'
    root_dir = os.getcwd()
    if root_dir[-2:] != "UI": 
        os.chdir("UI")
    main()