from django.db import models
from django.core.validators import MinLengthValidator

class Theme(models.Model):
    name = models.CharField(
        max_length=100, 
        unique=True, 
        validators=[MinLengthValidator(2)]
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Themes"

    def __str__(self):
        return self.name

class Room(models.Model):
    theme = models.ForeignKey(
        Theme, 
        on_delete=models.CASCADE, 
        related_name='rooms'
    )
    name = models.CharField(
        max_length=100, 
        unique=True, 
        validators=[MinLengthValidator(2)]
    )
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ['theme', 'name']
        ordering = ['theme', 'name']

    def __str__(self):
        return f"{self.theme.name} - {self.name}"

class Element(models.Model):
    room = models.ForeignKey(
        Room, 
        on_delete=models.CASCADE, 
        related_name='elements'
    )
    name = models.CharField(
        max_length=100, 
        validators=[MinLengthValidator(2)]
    )
    puzzle = models.TextField()
    hint = models.TextField()
    solved = models.BooleanField(default=False)
    difficulty = models.IntegerField(
        default=1, 
        choices=[(1, 'Easy'), (2, 'Medium'), (3, 'Hard')]
    )

    class Meta:
        unique_together = ['room', 'name']
        ordering = ['room', 'name']

    def __str__(self):
        return f"{self.room.name} - {self.name}"

class Answer(models.Model):
    element = models.ForeignKey(
        Element, 
        on_delete=models.CASCADE, 
        related_name='answers'
    )
    answer = models.CharField(
        max_length=100, 
        validators=[MinLengthValidator(1)]
    )

    class Meta:
        unique_together = ['element', 'answer']
        verbose_name_plural = "Answers"

    def __str__(self):
        return f"{self.element.name}: {self.answer}"
    
class UserGameSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True)
    solved_elements = models.JSONField(default=dict)
    current_theme = models.CharField(max_length=100, null=True, blank=True)
    score = models.IntegerField(default=0)
    lives = models.IntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chatbot_usergamesession'

    def __str__(self):
        return f"Session {self.session_id}"
