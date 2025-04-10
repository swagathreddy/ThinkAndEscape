class ContextManager:
    def __init__(self):
        self.user_context = {}

    def initialize_user(self, user_id):
        self.user_context[user_id] = {
            "current_room": "Library",
            "progress": [],
            "hints_used": 0,
        }

    def update_room(self, user_id, room):
        if user_id in self.user_context:
            self.user_context[user_id]["current_room"] = room

    def get_context(self, user_id):
        return self.user_context.get(user_id, None)
