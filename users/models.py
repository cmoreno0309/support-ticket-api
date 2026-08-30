from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Usuario del sistema. El rol determina qué puede ver y hacer (spec.md §3)."""

    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        AGENT = "AGENT", "Agent"

    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )

    @property
    def is_agent(self) -> bool:
        return self.role == self.Role.AGENT

    @property
    def is_customer(self) -> bool:
        return self.role == self.Role.CUSTOMER

    def __str__(self) -> str:
        return self.username
