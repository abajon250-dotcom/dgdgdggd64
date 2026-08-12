from .start import router as start_router
from .vk_accs import router as vk_router
from .admin import router as admin_router
from .broadcast import router as mailing_router

__all__ = ["start_router", "vk_router", "admin_router", "mailing_router"]