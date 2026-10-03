"""THE FIXED APP. This file's bytes are the thing we hash. It never changes."""
import dspy
from dspy.experimental import Choice, Noul

Move = Choice[("north", "toward the exit"), ("south", "away from the exit")]
Playable = Noul[(True, "the player can act"), (False, "the player must stop")]

class Room(dspy.Signature):
    """Decide the next move for a dungeon crawler."""
    room: str = dspy.InputField(desc="The room description.")
    move: Move = dspy.OutputField(desc="Which legal move?")
    can_act: Playable = dspy.OutputField(desc="Is the game still live?")

class Dungeon(dspy.Module):
    def __init__(self):
        super().__init__()
        self.legal = ["north", "south"]
        self.pick = dspy.Predict(Room)
    def forward(self, room):
        return self.pick(room=room)
