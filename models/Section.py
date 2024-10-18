class Section:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.num_measures = 0
        self.strum_pattern = "" # selected strum pattern option
        self.left_arm = []
        self.right_arm = []