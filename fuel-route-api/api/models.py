from django.db import models


class FuelStation(models.Model):
    opis_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=10, blank=True)
    lat = models.FloatField(db_index=True)
    lng = models.FloatField(db_index=True)
    price_per_gallon = models.FloatField()

    class Meta:
        indexes = [models.Index(fields=['lat', 'lng'])]

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state}) — ${self.price_per_gallon:.3f}"
