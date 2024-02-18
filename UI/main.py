from Controller import Controller
from Model import Model
from View import View

def main():
    model = Model()
    view = View()
    controller = Controller(view, model)
    controller.start()

# run this script to start the UI
if __name__ == "__main__":
    main()